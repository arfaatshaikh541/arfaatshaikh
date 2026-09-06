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


if __name__ == "__main__":
    main()
