"""Imports every SQLAlchemy model so `Base.metadata` is fully populated
before Alembic autogenerate or `Base.metadata.create_all` runs. Import
this module (not the individual model modules) wherever the complete
metadata is required.
"""

from app.core.db import Base  # noqa: F401
from app.modules.audit.models import AuditLog, PlatformAuditLog  # noqa: F401
from app.modules.campaign_jobs.models import CampaignJob, CampaignTask  # noqa: F401
from app.modules.campaigns.models import (  # noqa: F401
    Campaign,
    CampaignError,
    CampaignEvent,
    CampaignFilter,
    CampaignUsageEstimate,
)
from app.modules.identity.models import (  # noqa: F401
    EmailVerificationToken,
    PasswordResetToken,
    Session,
    User,
)
from app.modules.permissions.models import (  # noqa: F401
    Permission,
    PlatformRoleAssignment,
    Role,
    RolePermission,
)
from app.modules.platform_admin.models import SupportAccessGrant  # noqa: F401
from app.modules.subscriptions.models import (  # noqa: F401
    AddOn,
    Feature,
    FeatureOverride,
    PlanFeature,
    SubscriptionPlan,
    TenantAddOn,
    TenantSubscription,
)
from app.modules.tenancy.models import Invitation, Membership, Tenant, TenantSettings  # noqa: F401
from app.modules.usage.models import (  # noqa: F401
    CreditReservation,
    CreditTransaction,
    CreditWallet,
    UsageMetric,
    UsageRecord,
)
