from __future__ import annotations

import uuid
from datetime import UTC, datetime

from gridkeep_connector_sdk.base import ActionSpec
from gridkeep_connector_sdk.registry import get_connector_class
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import NotFoundError, ValidationAppError
from modules.actions.models import ActionRun, Playbook, TenantAutomationSetting
from modules.actions.policy import creates_action_run_for_playbook_match, is_playbook_action_auto_approved
from modules.assets.models import Asset
from modules.findings.models import Finding
from modules.findings.rules import RULES
from modules.integrations.models import IntegrationCatalogEntry, TenantIntegration

_VALID_RULE_KEYS = {rule.key for rule in RULES}


def _now() -> datetime:
    return datetime.now(UTC)


async def get_automation_mode(session: AsyncSession, *, tenant_id: uuid.UUID) -> str:
    setting = (
        await session.execute(
            select(TenantAutomationSetting).where(TenantAutomationSetting.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    return setting.mode if setting else "observe"


async def set_automation_mode(
    session: AsyncSession, *, tenant_id: uuid.UUID, mode: str, actor_user_id: uuid.UUID
) -> TenantAutomationSetting:
    setting = (
        await session.execute(
            select(TenantAutomationSetting).where(TenantAutomationSetting.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if setting is None:
        setting = TenantAutomationSetting(tenant_id=tenant_id, mode=mode, updated_by_user_id=actor_user_id)
        session.add(setting)
    else:
        setting.mode = mode
        setting.updated_by_user_id = actor_user_id
    await session.flush()
    return setting


async def list_playbooks(session: AsyncSession, *, tenant_id: uuid.UUID) -> list[Playbook]:
    result = await session.execute(
        select(Playbook).where(Playbook.tenant_id == tenant_id).order_by(Playbook.created_at.desc())
    )
    return list(result.scalars().all())


async def _get_playbook_or_404(
    session: AsyncSession, *, tenant_id: uuid.UUID, playbook_id: uuid.UUID
) -> Playbook:
    playbook = (
        await session.execute(
            select(Playbook).where(Playbook.id == playbook_id, Playbook.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if playbook is None:
        raise NotFoundError("Playbook not found.")
    return playbook


def _validate_rule_key(rule_key: str) -> None:
    if rule_key not in _VALID_RULE_KEYS:
        raise ValidationAppError(f"Unknown rule_key '{rule_key}'.")


async def create_playbook(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    name: str,
    description: str,
    rule_key: str,
    action_key: str,
    is_enabled: bool,
) -> Playbook:
    _validate_rule_key(rule_key)
    playbook = Playbook(
        tenant_id=tenant_id,
        name=name,
        description=description,
        rule_key=rule_key,
        action_key=action_key,
        is_enabled=is_enabled,
        created_by_user_id=actor_user_id,
    )
    session.add(playbook)
    await session.flush()
    return playbook


async def update_playbook(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    playbook_id: uuid.UUID,
    name: str | None,
    description: str | None,
    rule_key: str | None,
    action_key: str | None,
    is_enabled: bool | None,
) -> Playbook:
    playbook = await _get_playbook_or_404(session, tenant_id=tenant_id, playbook_id=playbook_id)
    if rule_key is not None:
        _validate_rule_key(rule_key)
        playbook.rule_key = rule_key
    if name is not None:
        playbook.name = name
    if description is not None:
        playbook.description = description
    if action_key is not None:
        playbook.action_key = action_key
    if is_enabled is not None:
        playbook.is_enabled = is_enabled
    await session.flush()
    return playbook


async def delete_playbook(session: AsyncSession, *, tenant_id: uuid.UUID, playbook_id: uuid.UUID) -> None:
    playbook = await _get_playbook_or_404(session, tenant_id=tenant_id, playbook_id=playbook_id)
    await session.delete(playbook)
    await session.flush()


async def _get_asset_and_integration(
    session: AsyncSession, *, tenant_id: uuid.UUID, asset_id: uuid.UUID
) -> tuple[Asset, TenantIntegration, str]:
    asset = (
        await session.execute(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if asset is None:
        raise NotFoundError("Asset not found.")
    if asset.tenant_integration_id is None:
        raise ValidationAppError("This asset has no source integration to execute an action through.")

    row = (
        await session.execute(
            select(TenantIntegration, IntegrationCatalogEntry.provider_id)
            .join(
                IntegrationCatalogEntry, IntegrationCatalogEntry.id == TenantIntegration.catalog_entry_id
            )
            .where(
                TenantIntegration.id == asset.tenant_integration_id,
                TenantIntegration.tenant_id == tenant_id,
            )
        )
    ).one_or_none()
    if row is None:
        raise NotFoundError("Source integration for this asset no longer exists.")
    tenant_integration, provider_id = row
    return asset, tenant_integration, provider_id


def _resolve_action_spec(provider_id: str, action_key: str) -> ActionSpec:
    connector_class = get_connector_class(provider_id)
    for spec in connector_class.definition.supported_actions:
        if spec.key == action_key:
            return spec
    raise ValidationAppError(f"Provider '{provider_id}' does not support action '{action_key}'.")


async def get_action_catalog_for_asset(
    session: AsyncSession, *, tenant_id: uuid.UUID, asset_id: uuid.UUID
) -> list[ActionSpec]:
    _, _, provider_id = await _get_asset_and_integration(session, tenant_id=tenant_id, asset_id=asset_id)
    connector_class = get_connector_class(provider_id)
    return list(connector_class.definition.supported_actions)


async def list_action_runs(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    status: str | None = None,
    asset_id: uuid.UUID | None = None,
    finding_id: uuid.UUID | None = None,
) -> list[tuple[ActionRun, Asset]]:
    query = (
        select(ActionRun, Asset)
        .join(Asset, Asset.id == ActionRun.asset_id)
        .where(ActionRun.tenant_id == tenant_id)
    )
    if status:
        query = query.where(ActionRun.status == status)
    if asset_id:
        query = query.where(ActionRun.asset_id == asset_id)
    if finding_id:
        query = query.where(ActionRun.finding_id == finding_id)
    query = query.order_by(ActionRun.requested_at.desc())
    result = await session.execute(query)
    return [(run, asset) for run, asset in result.all()]


async def _get_action_run_or_404(
    session: AsyncSession, *, tenant_id: uuid.UUID, action_run_id: uuid.UUID
) -> tuple[ActionRun, Asset]:
    row = (
        await session.execute(
            select(ActionRun, Asset)
            .join(Asset, Asset.id == ActionRun.asset_id)
            .where(ActionRun.id == action_run_id, ActionRun.tenant_id == tenant_id)
        )
    ).one_or_none()
    if row is None:
        raise NotFoundError("Action run not found.")
    return row


async def get_action_run_detail(
    session: AsyncSession, *, tenant_id: uuid.UUID, action_run_id: uuid.UUID
) -> tuple[ActionRun, Asset]:
    return await _get_action_run_or_404(session, tenant_id=tenant_id, action_run_id=action_run_id)


async def request_manual_action(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_can_approve_disruptive: bool,
    asset_id: uuid.UUID,
    action_key: str,
    params: dict,
    finding_id: uuid.UUID | None,
) -> tuple[ActionRun, Asset]:
    """A human explicitly requested this — the tenant's automation `mode`
    plays no part here. What gates immediate execution is the actor's own
    permission: anyone with `actions.execute_safe` can request any action,
    but it only executes immediately if the actor also holds
    `actions.approve_disruptive` or the action's safety class is 0-1.
    Otherwise it waits in `pending_approval` for someone who does."""
    asset, tenant_integration, provider_id = await _get_asset_and_integration(
        session, tenant_id=tenant_id, asset_id=asset_id
    )
    spec = _resolve_action_spec(provider_id, action_key)

    if finding_id is not None:
        finding_exists = (
            await session.execute(
                select(Finding.id).where(Finding.id == finding_id, Finding.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if finding_exists is None:
            raise NotFoundError("Finding not found.")

    now = _now()
    auto_approved = spec.safety_class <= 1 or actor_can_approve_disruptive
    run = ActionRun(
        tenant_id=tenant_id,
        action_key=spec.key,
        provider_id=provider_id,
        safety_class=spec.safety_class,
        tenant_integration_id=tenant_integration.id,
        asset_id=asset.id,
        finding_id=finding_id,
        playbook_id=None,
        trigger="manual",
        status="approved" if auto_approved else "pending_approval",
        params=params,
        requested_by_user_id=actor_user_id,
        approved_by_user_id=actor_user_id if auto_approved else None,
        requested_at=now,
        decided_at=now if auto_approved else None,
    )
    session.add(run)
    await session.flush()
    return run, asset


async def approve_action_run(
    session: AsyncSession, *, tenant_id: uuid.UUID, action_run_id: uuid.UUID, actor_user_id: uuid.UUID
) -> tuple[ActionRun, Asset]:
    run, asset = await _get_action_run_or_404(session, tenant_id=tenant_id, action_run_id=action_run_id)
    if run.status != "pending_approval":
        raise ValidationAppError(f"Action run is '{run.status}', not pending approval.")
    run.status = "approved"
    run.approved_by_user_id = actor_user_id
    run.decided_at = _now()
    await session.flush()
    return run, asset


async def reject_action_run(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    action_run_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    reason: str,
) -> tuple[ActionRun, Asset]:
    run, asset = await _get_action_run_or_404(session, tenant_id=tenant_id, action_run_id=action_run_id)
    if run.status != "pending_approval":
        raise ValidationAppError(f"Action run is '{run.status}', not pending approval.")
    run.status = "rejected"
    run.approved_by_user_id = actor_user_id
    run.decided_at = _now()
    run.result_message = reason
    await session.flush()
    return run, asset


async def evaluate_playbooks_for_findings(
    session: AsyncSession, *, tenant_id: uuid.UUID, finding_ids: list[uuid.UUID]
) -> list[ActionRun]:
    """Called after correlation for every newly-created or reopened
    finding. Never raises on a mismatched/misconfigured playbook (e.g. an
    action_key the asset's current provider doesn't support) — a bad
    playbook should not break correlation; it's simply skipped for that
    finding."""
    if not finding_ids:
        return []

    mode = await get_automation_mode(session, tenant_id=tenant_id)
    if not creates_action_run_for_playbook_match(mode):
        return []

    findings = (
        await session.execute(
            select(Finding).where(Finding.tenant_id == tenant_id, Finding.id.in_(finding_ids))
        )
    ).scalars().all()
    if not findings:
        return []

    rule_keys = {f.rule_key for f in findings}
    playbooks = (
        await session.execute(
            select(Playbook).where(
                Playbook.tenant_id == tenant_id,
                Playbook.is_enabled.is_(True),
                Playbook.rule_key.in_(rule_keys),
            )
        )
    ).scalars().all()
    if not playbooks:
        return []
    playbooks_by_rule: dict[str, list[Playbook]] = {}
    for pb in playbooks:
        playbooks_by_rule.setdefault(pb.rule_key, []).append(pb)

    now = _now()
    created_runs: list[ActionRun] = []
    for finding in findings:
        matching = playbooks_by_rule.get(finding.rule_key, [])
        for playbook in matching:
            try:
                asset, tenant_integration, provider_id = await _get_asset_and_integration(
                    session, tenant_id=tenant_id, asset_id=finding.asset_id
                )
                spec = _resolve_action_spec(provider_id, playbook.action_key)
            except (NotFoundError, ValidationAppError):
                continue

            auto_approved = is_playbook_action_auto_approved(mode, spec.safety_class)
            run = ActionRun(
                tenant_id=tenant_id,
                action_key=spec.key,
                provider_id=provider_id,
                safety_class=spec.safety_class,
                tenant_integration_id=tenant_integration.id,
                asset_id=asset.id,
                finding_id=finding.id,
                playbook_id=playbook.id,
                trigger="playbook",
                status="approved" if auto_approved else "pending_approval",
                params={},
                requested_by_user_id=None,
                approved_by_user_id=None,
                requested_at=now,
                decided_at=now if auto_approved else None,
            )
            session.add(run)
            created_runs.append(run)

    if created_runs:
        await session.flush()
    return created_runs
