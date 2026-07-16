from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import (
    TenantContext,
    get_tenant_db,
    require_csrf,
    require_permission,
    require_step_up,
    require_tenant_write,
)
from core.task_queue import enqueue_run_action
from modules.actions import service as actions_service
from modules.actions.models import ActionRun
from modules.actions.schemas import (
    ActionCatalogEntry,
    ActionRunRead,
    AutomationSettingRead,
    AutomationSettingUpdateRequest,
    ExecuteActionRequest,
    PlaybookCreateRequest,
    PlaybookRead,
    PlaybookUpdateRequest,
    RejectActionRequest,
    RunActionResponse,
)
from modules.assets.models import Asset
from modules.audit import service as audit_service

actions_router = APIRouter(prefix="/api/actions", tags=["actions"])
playbooks_router = APIRouter(prefix="/api/playbooks", tags=["playbooks"])
automation_router = APIRouter(prefix="/api/automation", tags=["automation"])


def _to_action_run_read(run: ActionRun, asset: Asset) -> ActionRunRead:
    return ActionRunRead(
        id=run.id,
        action_key=run.action_key,
        provider_id=run.provider_id,
        safety_class=run.safety_class,
        status=run.status,
        trigger=run.trigger,
        asset_id=asset.id,
        asset_display_name=asset.display_name,
        finding_id=run.finding_id,
        playbook_id=run.playbook_id,
        params=run.params,
        result_message=run.result_message,
        requested_at=run.requested_at,
        decided_at=run.decided_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


@actions_router.get("/catalog", response_model=list[ActionCatalogEntry])
async def get_action_catalog(
    asset_id: uuid.UUID = Query(...),
    ctx: TenantContext = Depends(require_permission("actions.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[ActionCatalogEntry]:
    specs = await actions_service.get_action_catalog_for_asset(
        db, tenant_id=ctx.tenant_id, asset_id=asset_id
    )
    return [
        ActionCatalogEntry(
            action_key=s.key, name=s.name, safety_class=s.safety_class, reversible=s.reversible
        )
        for s in specs
    ]


@actions_router.get("", response_model=list[ActionRunRead])
async def list_action_runs(
    status: str | None = Query(default=None),
    asset_id: uuid.UUID | None = Query(default=None),
    finding_id: uuid.UUID | None = Query(default=None),
    ctx: TenantContext = Depends(require_permission("actions.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[ActionRunRead]:
    rows = await actions_service.list_action_runs(
        db, tenant_id=ctx.tenant_id, status=status, asset_id=asset_id, finding_id=finding_id
    )
    return [_to_action_run_read(run, asset) for run, asset in rows]


@actions_router.get("/{action_run_id}", response_model=ActionRunRead)
async def get_action_run(
    action_run_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("actions.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> ActionRunRead:
    run, asset = await actions_service.get_action_run_detail(
        db, tenant_id=ctx.tenant_id, action_run_id=action_run_id
    )
    return _to_action_run_read(run, asset)


@actions_router.post("/execute", response_model=RunActionResponse, dependencies=[Depends(require_csrf)])
async def execute_action(
    payload: ExecuteActionRequest,
    ctx: TenantContext = Depends(require_permission("actions.execute_safe")),
    db: AsyncSession = Depends(get_tenant_db),
) -> RunActionResponse:
    require_tenant_write(ctx)
    run, asset = await actions_service.request_manual_action(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_can_approve_disruptive=ctx.has_permission("actions.approve_disruptive"),
        asset_id=payload.asset_id,
        action_key=payload.action_key,
        params=payload.params,
        finding_id=payload.finding_id,
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="actions.requested",
        target_type="action_run",
        target_id=str(run.id),
        context={"action_key": run.action_key, "asset_id": str(asset.id), "status": run.status},
    )
    response = RunActionResponse(action_run=_to_action_run_read(run, asset), task_id=None)
    is_approved = run.status == "approved"
    run_id = run.id
    await db.commit()

    if is_approved:
        response.task_id = enqueue_run_action(str(ctx.tenant_id), str(run_id))
    return response


@actions_router.post(
    "/{action_run_id}/approve",
    response_model=RunActionResponse,
    dependencies=[Depends(require_csrf), Depends(require_step_up())],
)
async def approve_action_run(
    action_run_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("actions.approve_disruptive")),
    db: AsyncSession = Depends(get_tenant_db),
) -> RunActionResponse:
    """Step-up (a recent, separately-verified MFA code) is required here
    for any user who has MFA enabled — the exact use case
    `core.deps.require_step_up`'s docstring has named since Milestone 1
    ("disruptive-action approval"). See Milestone 13's Known Limitations
    for why this doesn't yet also read
    `TenantSecurityProfile.require_step_up_for_disruptive_actions` to make
    MFA itself mandatory for admins tenant-wide."""
    require_tenant_write(ctx)
    run, asset = await actions_service.approve_action_run(
        db, tenant_id=ctx.tenant_id, action_run_id=action_run_id, actor_user_id=ctx.user.id
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="actions.approved",
        target_type="action_run",
        target_id=str(run.id),
    )
    response = RunActionResponse(action_run=_to_action_run_read(run, asset), task_id=None)
    run_id = run.id
    await db.commit()
    response.task_id = enqueue_run_action(str(ctx.tenant_id), str(run_id))
    return response


@actions_router.post(
    "/{action_run_id}/reject", response_model=ActionRunRead, dependencies=[Depends(require_csrf)]
)
async def reject_action_run(
    action_run_id: uuid.UUID,
    payload: RejectActionRequest,
    ctx: TenantContext = Depends(require_permission("actions.approve_disruptive")),
    db: AsyncSession = Depends(get_tenant_db),
) -> ActionRunRead:
    require_tenant_write(ctx)
    run, asset = await actions_service.reject_action_run(
        db,
        tenant_id=ctx.tenant_id,
        action_run_id=action_run_id,
        actor_user_id=ctx.user.id,
        reason=payload.reason,
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="actions.rejected",
        target_type="action_run",
        target_id=str(run.id),
        context={"reason": payload.reason},
    )
    response = _to_action_run_read(run, asset)
    await db.commit()
    return response


@playbooks_router.get("", response_model=list[PlaybookRead])
async def list_playbooks(
    ctx: TenantContext = Depends(require_permission("playbooks.view")),
    db: AsyncSession = Depends(get_tenant_db),
) -> list[PlaybookRead]:
    playbooks = await actions_service.list_playbooks(db, tenant_id=ctx.tenant_id)
    return [PlaybookRead.model_validate(p) for p in playbooks]


@playbooks_router.post("", response_model=PlaybookRead, dependencies=[Depends(require_csrf)])
async def create_playbook(
    payload: PlaybookCreateRequest,
    ctx: TenantContext = Depends(require_permission("playbooks.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> PlaybookRead:
    require_tenant_write(ctx)
    playbook = await actions_service.create_playbook(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        name=payload.name,
        description=payload.description,
        rule_key=payload.rule_key,
        action_key=payload.action_key,
        is_enabled=payload.is_enabled,
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="playbooks.created",
        target_type="playbook",
        target_id=str(playbook.id),
        context={"rule_key": payload.rule_key, "action_key": payload.action_key},
    )
    response = PlaybookRead.model_validate(playbook)
    await db.commit()
    return response


@playbooks_router.patch("/{playbook_id}", response_model=PlaybookRead, dependencies=[Depends(require_csrf)])
async def update_playbook(
    playbook_id: uuid.UUID,
    payload: PlaybookUpdateRequest,
    ctx: TenantContext = Depends(require_permission("playbooks.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> PlaybookRead:
    require_tenant_write(ctx)
    playbook = await actions_service.update_playbook(
        db,
        tenant_id=ctx.tenant_id,
        playbook_id=playbook_id,
        name=payload.name,
        description=payload.description,
        rule_key=payload.rule_key,
        action_key=payload.action_key,
        is_enabled=payload.is_enabled,
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="playbooks.updated",
        target_type="playbook",
        target_id=str(playbook.id),
    )
    response = PlaybookRead.model_validate(playbook)
    await db.commit()
    return response


@playbooks_router.delete("/{playbook_id}", dependencies=[Depends(require_csrf)])
async def delete_playbook(
    playbook_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission("playbooks.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> dict:
    require_tenant_write(ctx)
    await actions_service.delete_playbook(db, tenant_id=ctx.tenant_id, playbook_id=playbook_id)
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="playbooks.deleted",
        target_type="playbook",
        target_id=str(playbook_id),
    )
    await db.commit()
    return {"status": "ok"}


@automation_router.get("/settings", response_model=AutomationSettingRead)
async def get_automation_settings(
    ctx: TenantContext = Depends(require_permission("automations.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> AutomationSettingRead:
    mode = await actions_service.get_automation_mode(db, tenant_id=ctx.tenant_id)
    return AutomationSettingRead(mode=mode)


@automation_router.patch(
    "/settings", response_model=AutomationSettingRead, dependencies=[Depends(require_csrf)]
)
async def update_automation_settings(
    payload: AutomationSettingUpdateRequest,
    ctx: TenantContext = Depends(require_permission("automations.manage")),
    db: AsyncSession = Depends(get_tenant_db),
) -> AutomationSettingRead:
    require_tenant_write(ctx)
    await actions_service.set_automation_mode(
        db, tenant_id=ctx.tenant_id, mode=payload.mode, actor_user_id=ctx.user.id
    )
    await audit_service.record(
        db,
        tenant_id=ctx.tenant_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        action="automation.mode_changed",
        context={"mode": payload.mode},
    )
    await db.commit()
    return AutomationSettingRead(mode=payload.mode)
