from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db, set_platform_bypass
from app.core.exceptions import ValidationAppError
from app.dependencies import TenantContext, require_permission
from app.modules.billing import repositories as billing_repo
from app.modules.billing import services
from app.modules.billing.schemas import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    InvoiceListResponse,
    InvoiceResponse,
    PortalSessionResponse,
)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    body: CheckoutSessionRequest,
    ctx: TenantContext = Depends(require_permission("billing.manage")),
    db: AsyncSession = Depends(get_db),
):
    url = await services.create_checkout_session(
        db, tenant_id=ctx.tenant_id, requesting_user_id=ctx.user_id, plan_key=body.plan_key
    )
    await db.commit()
    return CheckoutSessionResponse(checkout_url=url)


@router.post("/portal-session", response_model=PortalSessionResponse)
async def create_portal_session(
    ctx: TenantContext = Depends(require_permission("billing.manage")),
    db: AsyncSession = Depends(get_db),
):
    url = await services.create_portal_session(
        db, tenant_id=ctx.tenant_id, requesting_user_id=ctx.user_id
    )
    return PortalSessionResponse(portal_url=url)


@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    ctx: TenantContext = Depends(require_permission("billing.view")),
    db: AsyncSession = Depends(get_db),
):
    invoices = await billing_repo.list_invoices_for_tenant(db, ctx.tenant_id)
    return InvoiceListResponse(
        invoices=[InvoiceResponse.model_validate(i, from_attributes=True) for i in invoices]
    )


@router.post("/webhook", status_code=200)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receives real, signed events from Stripe - the sole source of
    truth for subscription/invoice state (see `services.handle_webhook_
    event`'s module docstring). Deliberately outside the normal
    session-cookie/CSRF/permission dependency chain: Stripe calls this
    server-to-server with no session and no CSRF token, authenticated
    instead by its own HMAC signature over the raw request body.

    `set_platform_bypass` is used here for the same reason ADR-0007
    sanctions it for invitation-accept-by-token and the worker's own
    task lookups: the tenant isn't known until a unique external key
    (the Stripe customer/event id) resolves it, and every write that
    follows is scoped to exactly that one resolved tenant_id - never a
    bulk, attacker-influenced cross-tenant scan.
    """
    signature_header = request.headers.get("stripe-signature")
    if not signature_header:
        raise ValidationAppError("Missing Stripe-Signature header.")
    raw_body = await request.body()

    await set_platform_bypass(db)
    await services.handle_webhook_event(db, payload=raw_body, signature_header=signature_header)
    await db.commit()
    return {"received": True}
