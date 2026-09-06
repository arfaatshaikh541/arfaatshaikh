"""Headless CLI client.

There is no native Windows shell in this build (this environment cannot
build or run one — see core/RUNBOOK.md). This CLI is the real, working
interface for now, including the owner-facing controls for the Action
Broker: approvals, the kill switch, and audit inspection.
"""
from __future__ import annotations

import asyncio
import sys

import click

from .providers import NoProviderAvailable
from .runtime import build_runtime
from .status import registry as status_registry


@click.group()
def main() -> None:
    """AURA headless core CLI."""


@main.command()
def status() -> None:
    """Print real capability status (health-checks the model provider)."""
    runtime = build_runtime()

    async def _check() -> None:
        try:
            await runtime.model_router.select_provider()
        except NoProviderAvailable:
            pass  # status registry already recorded the honest reason

    asyncio.run(_check())

    for name, info in status_registry.snapshot().items():
        click.echo(f"{name:30s} {info['status']:18s} {info['detail']}")


@main.command()
def chat() -> None:
    """Interactive chat loop. Known commands route through the Action
    Broker (kill-switch/policy/risk/audit-gated); everything else goes to
    the model lane with real streaming output."""
    runtime = build_runtime()

    async def _loop() -> None:
        click.echo("AURA core chat. Type 'exit' to quit.")
        while True:
            try:
                text = input("you> ").strip()
            except EOFError:
                break
            if text.lower() in {"exit", "quit"}:
                break
            if not text:
                continue

            action_request = runtime.triggers.resolve(text)
            if action_request is not None:
                outcome = runtime.broker.submit(action_request)
                click.echo(f"aura [{outcome.status.value}]> {outcome.message}")
                continue

            sys.stdout.write("aura> ")
            sys.stdout.flush()
            try:
                async for chunk in runtime.model_router.generate_stream(text, history=[]):
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
            except NoProviderAvailable as exc:
                sys.stdout.write(f"\n[unavailable] {exc}")
            sys.stdout.write("\n")

    asyncio.run(_loop())


@main.group()
def approvals() -> None:
    """Inspect and decide on pending Action Broker approvals."""


@approvals.command("list")
def approvals_list() -> None:
    runtime = build_runtime()
    pending = runtime.approvals.pending()
    if not pending:
        click.echo("No pending approvals.")
        return
    for record in pending:
        click.echo(
            f"{record.id}  [{record.risk_tier}]  {record.action_type}  "
            f"requested_by={record.requested_by}  reason={record.reason}"
        )


@approvals.command("decide")
@click.argument("approval_id")
@click.option("--approve/--deny", "approved", required=True)
@click.option("--by", "decided_by", default="owner")
def approvals_decide(approval_id: str, approved: bool, decided_by: str) -> None:
    runtime = build_runtime()
    outcome = runtime.broker.resume_after_approval(approval_id, approved=approved, decided_by=decided_by)
    click.echo(f"[{outcome.status.value}] {outcome.message}")


@main.group("kill-switch")
def kill_switch() -> None:
    """Engage or disengage the global kill switch."""


@kill_switch.command("engage")
def kill_switch_engage() -> None:
    runtime = build_runtime()
    runtime.policy.engage_kill_switch()
    click.echo("Kill switch ENGAGED. No actions will execute until disengaged.")


@kill_switch.command("disengage")
def kill_switch_disengage() -> None:
    runtime = build_runtime()
    runtime.policy.disengage_kill_switch()
    click.echo("Kill switch disengaged.")


@kill_switch.command("status")
def kill_switch_status() -> None:
    runtime = build_runtime()
    engaged = runtime.policy.is_kill_switch_engaged()
    click.echo(f"kill_switch_engaged: {engaged}")


@main.group()
def audit() -> None:
    """Inspect the tamper-evident audit log."""


@audit.command("show")
@click.option("--limit", default=20, help="Show only the last N entries.")
def audit_show(limit: int) -> None:
    runtime = build_runtime()
    entries = runtime.audit.all_entries()[-limit:]
    for entry in entries:
        click.echo(
            f"#{entry.seq} {entry.timestamp_iso} actor={entry.actor} "
            f"action={entry.action_type} risk={entry.risk_tier} decision={entry.decision} "
            f"result={entry.result_status} :: {entry.result_message}"
        )


@audit.command("verify")
def audit_verify() -> None:
    runtime = build_runtime()
    verification = runtime.audit.verify_chain()
    if verification.valid:
        click.echo(f"OK: chain valid across {verification.entries_checked} entries.")
    else:
        click.echo(f"TAMPERED: chain broken at seq={verification.broken_at_seq}.", err=True)
        raise SystemExit(1)


@main.group()
def guardian() -> None:
    """Inspect Security Guardian and trigger a manual freeze."""


@guardian.command("events")
@click.option("--limit", default=20)
def guardian_events(limit: int) -> None:
    runtime = build_runtime()
    for event in runtime.guardian.recent_events(limit=limit):
        click.echo(f"{event.detected_at} [{event.action_taken}] {event.rule_name}: {event.detail}")


@guardian.command("freeze")
@click.argument("reason")
def guardian_freeze(reason: str) -> None:
    runtime = build_runtime()
    event = runtime.guardian.freeze(reason)
    click.echo(f"Frozen. Guardian event {event.id} recorded.")


@main.group()
def connectors() -> None:
    """Inspect registered connectors and their real, live-checked health."""


@connectors.command("list")
def connectors_list() -> None:
    runtime = build_runtime()
    runtime.connectors.refresh_all()
    snapshot = status_registry.snapshot()
    for manifest in runtime.connectors.manifests():
        info = snapshot.get(f"connector.{manifest.name}", {})
        click.echo(f"{manifest.name:16s} {info.get('status', 'UNKNOWN'):18s} {info.get('detail', '')}")
        click.echo(f"{'':16s} auth={manifest.auth_method} capabilities={', '.join(manifest.capabilities)}")


@main.group()
def tasks() -> None:
    """Inspect and enqueue durable background tasks."""


@tasks.command("list")
@click.option("--status", default=None)
def tasks_list(status: str | None) -> None:
    runtime = build_runtime()
    statuses = [status] if status else ["QUEUED", "RUNNING", "WAITING", "BLOCKED", "NEEDS_APPROVAL", "RETRYING"]
    for s in statuses:
        for task in runtime.tasks.list_by_status(s):
            click.echo(f"{task.id} [{task.status}] {task.task_type} attempts={task.attempts}/{task.max_attempts}")


@tasks.command("enqueue")
@click.argument("task_type")
@click.option("--payload", default="{}", help="JSON payload")
def tasks_enqueue(task_type: str, payload: str) -> None:
    import json as _json

    runtime = build_runtime()
    task = runtime.tasks.enqueue(task_type, _json.loads(payload))
    click.echo(f"Enqueued {task.id} [{task.status}]")


@main.group()
def goals() -> None:
    """Create, activate, and review goals."""


@goals.command("create")
@click.argument("statement")
@click.option("--success-metric", default=None)
@click.option("--budget", default=None, help="JSON budget object")
@click.option("--stop-condition", "stop_conditions", multiple=True)
@click.option("--review-interval-seconds", default=86400, help="How often the executive re-reviews this goal.")
def goals_create(
    statement: str, success_metric: str | None, budget: str | None,
    stop_conditions: tuple[str, ...], review_interval_seconds: int,
) -> None:
    import json as _json

    runtime = build_runtime()
    goal = runtime.goals.create(
        statement, success_metric=success_metric,
        budget=_json.loads(budget) if budget else None,
        stop_conditions=list(stop_conditions),
        review_interval_seconds=review_interval_seconds,
    )
    click.echo(f"Created {goal.id} [{goal.status}]")


@goals.command("activate")
@click.argument("goal_id")
def goals_activate(goal_id: str) -> None:
    from .executive import GoalNotReadyError

    runtime = build_runtime()
    try:
        goal = runtime.goals.activate(goal_id)
        click.echo(f"[{goal.status}] {goal.id}")
    except GoalNotReadyError as exc:
        click.echo(f"Not ready: {exc}", err=True)
        raise SystemExit(1)


@goals.command("set-mandate")
@click.argument("goal_id")
@click.argument("mandate_id")
def goals_set_mandate(goal_id: str, mandate_id: str) -> None:
    """Link a goal as one of a mandate's workstreams -- what "Run
    Gridkeep" actually needs behind it: the persistent mandate on its
    own has nothing to report on until at least one workstream is
    attached to it this way."""
    runtime = build_runtime()
    runtime.goals.set_mandate(goal_id, mandate_id)
    click.echo(f"{goal_id} -> mandate {mandate_id}")


@goals.command("list")
def goals_list() -> None:
    runtime = build_runtime()
    for goal in runtime.goals.list_active():
        click.echo(f"{goal.id} [{goal.status}] progress={goal.progress:.0%} {goal.statement}")


@goals.command("review")
def goals_review() -> None:
    runtime = build_runtime()
    outcomes = asyncio.run(runtime.executive.run_review_cycle())
    if not outcomes:
        click.echo("No goals due for review.")
    for outcome in outcomes:
        if outcome.error:
            click.echo(f"{outcome.goal_id}: error: {outcome.error}")
        else:
            click.echo(f"{outcome.goal_id}: task {outcome.task_id} -- {outcome.decision.statement}")


@main.group()
def mandates() -> None:
    """Create, activate, and report on persistent mandates -- the
    "Run Gridkeep"-style directive that survives restarts and owns one
    or more workstreams (goals)."""


@mandates.command("create")
@click.argument("title")
@click.argument("mission")
@click.option("--objective", "objectives", multiple=True, required=True)
@click.option("--kpi", "kpis", multiple=True, help="JSON object, e.g. '{\"name\":\"x\",\"target\":1,\"current\":0}'")
@click.option("--constraint", "constraints", multiple=True, required=True)
def mandates_create(title: str, mission: str, objectives: tuple[str, ...], kpis: tuple[str, ...], constraints: tuple[str, ...]) -> None:
    import json as _json

    runtime = build_runtime()
    mandate = runtime.mandates.create(
        title, mission, objectives=list(objectives),
        kpis=[_json.loads(k) for k in kpis], constraints=list(constraints),
    )
    click.echo(f"Created {mandate.id} [{mandate.status}]")


@mandates.command("activate")
@click.argument("mandate_id")
def mandates_activate(mandate_id: str) -> None:
    from .executive import MandateNotReadyError

    runtime = build_runtime()
    try:
        mandate = runtime.mandates.activate(mandate_id)
        click.echo(f"[{mandate.status}] {mandate.id}")
    except MandateNotReadyError as exc:
        click.echo(f"Not ready: {exc}", err=True)
        raise SystemExit(1)


@mandates.command("list")
def mandates_list() -> None:
    runtime = build_runtime()
    for mandate in runtime.mandates.list_active():
        click.echo(f"{mandate.id} [{mandate.status}] {mandate.title}")


@mandates.command("report")
@click.argument("mandate_id")
def mandates_report(mandate_id: str) -> None:
    runtime = build_runtime()
    report = runtime.mandates.report(mandate_id, runtime.goals, runtime.memory)
    click.echo(f"{report.title} [{report.status}] -- generated {report.generated_at.isoformat()}")
    click.echo(f"Counts: {report.counts or 'no workstreams yet'}")
    for ws in report.workstreams:
        click.echo(f"  [{ws.bucket:18s}] {ws.statement} (progress={ws.progress:.0%})")
        if ws.latest_decision:
            click.echo(f"      last: {ws.latest_decision}")
    if report.blockers:
        click.echo("Blockers:")
        for b in report.blockers:
            click.echo(f"  - {b}")
    if report.next_actions:
        click.echo("Next actions:")
        for a in report.next_actions:
            click.echo(f"  - {a}")


@main.group()
def loop() -> None:
    """Run the autonomous operating loop: plan due workstreams, observe
    due mandates, drain and execute the resulting tasks through the
    real Action Broker, on a schedule, surviving restarts."""


@loop.command("run-once")
def loop_run_once() -> None:
    """One full cycle, synchronously, then exit -- useful for testing or
    for driving the loop from an external scheduler instead of the
    built-in background thread."""
    runtime = build_runtime()
    outcomes = asyncio.run(runtime.operating_loop.run_cycle_once())
    if not outcomes:
        click.echo("Nothing to do this cycle.")
    for outcome in outcomes:
        click.echo(f"{outcome.task_id} [{outcome.outcome}] {outcome.detail}")


@loop.command("run")
@click.option("--interval-seconds", default=30.0)
def loop_run(interval_seconds: float) -> None:
    """Run the operating loop forever in the foreground (Ctrl+C to
    stop) -- the actual autonomous heartbeat, not a one-shot demo."""
    runtime = build_runtime()
    runtime.operating_loop.interval_seconds = interval_seconds
    click.echo(f"Operating loop running every {interval_seconds}s. Ctrl+C to stop.")
    thread = runtime.operating_loop.start_in_background()
    try:
        thread.join()
    except KeyboardInterrupt:
        runtime.operating_loop.stop()


@main.group()
def memory() -> None:
    """Search AURA's memory, or ask it a free-text question answered
    from real retrieved records."""


@memory.command("search")
@click.argument("query")
@click.option("--limit", default=10)
def memory_search(query: str, limit: int) -> None:
    runtime = build_runtime()
    results = runtime.memory.search(query, limit=limit)
    if not results:
        click.echo("No matching memory found.")
    for r in results:
        click.echo(f"[{r.kind:10s} {r.score:.2f} {r.created_at.date().isoformat()}] {r.text}")


@memory.command("ask")
@click.argument("question")
def memory_ask(question: str) -> None:
    from .memory import answer_question

    runtime = build_runtime()
    result = asyncio.run(answer_question(question, runtime.memory, runtime.model_router))
    if result.error:
        click.echo(f"Could not answer: {result.error}", err=True)
        raise SystemExit(1)
    click.echo(result.answer)
    click.echo("")
    click.echo(f"(grounded in {len(result.context_used)} memory record(s))")


@main.group()
def voice() -> None:
    """Run and supervise the real-time voice pipeline
    (apps/voice/AuraVoice.Windows.Host)."""


@voice.command("run")
@click.option("--max-restarts", default=5, help="Give up after this many crashes in a row.")
@click.option("--backoff-seconds", default=2.0, help="Initial restart delay; doubles on each further crash.")
def voice_run(max_restarts: int, backoff_seconds: float) -> None:
    """Launch the C# voice pipeline host under the same Supervisor used
    for self-recovery elsewhere in AURA, so a crash (a transient audio-
    device error, a dropped connection) restarts the voice process with
    backoff instead of silently leaving AURA deaf until someone notices
    and restarts it by hand. Requires the .NET SDK; the process itself
    needs a real microphone/speaker to do anything useful -- see
    apps/voice/README.md for exactly what that requires."""
    from pathlib import Path

    from .diagnostics import Supervisor

    project_dir = Path(__file__).resolve().parents[3] / "apps" / "voice" / "AuraVoice.Windows.Host"
    if not project_dir.exists():
        raise click.ClickException(f"voice host project not found at {project_dir}")

    command = ["dotnet", "run", "--project", str(project_dir)]
    click.echo(f"Supervising: {' '.join(command)}")
    click.echo("Ctrl+C to stop.")

    supervisor = Supervisor(command, max_restarts=max_restarts, backoff_seconds=backoff_seconds)
    try:
        supervisor.start()
    except KeyboardInterrupt:
        supervisor.stop()
    for event in supervisor.events[-5:]:
        click.echo(f"  {event.at.isoformat()} [{event.kind}] {event.detail}")


@main.command()
def diagnose() -> None:
    """Print an aggregate diagnostic snapshot: capability status, audit
    chain integrity, and recent Security Guardian activity."""
    from .diagnostics import collect_diagnostics

    runtime = build_runtime()
    report = collect_diagnostics(runtime.audit, runtime.guardian)

    click.echo(f"Audit chain valid: {report.audit_chain_valid} ({report.audit_entries_checked} entries)")
    click.echo("Recent Guardian events:")
    if not report.recent_guardian_events:
        click.echo("  none")
    for event in report.recent_guardian_events:
        click.echo(f"  {event['detected_at']} [{event['action_taken']}] {event['rule_name']}: {event['detail']}")
    click.echo("Capability status:")
    for name, info in report.capability_status.items():
        click.echo(f"  {name:30s} {info['status']:18s} {info['detail']}")


if __name__ == "__main__":
    main()
