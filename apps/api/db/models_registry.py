"""Importing this module guarantees every module's SQLAlchemy models are
registered on Base.metadata before any ORM operation runs — needed
wherever cross-module foreign keys must resolve (Alembic env.py, seed
scripts, tests). Application routes never need this directly since
main.py's router imports transitively pull in every module already."""

from modules.audit import models as _audit_models  # noqa: F401
from modules.credential_vault import models as _credential_vault_models  # noqa: F401
from modules.entitlements import models as _entitlements_models  # noqa: F401
from modules.identity import models as _identity_models  # noqa: F401
from modules.permissions import models as _permissions_models  # noqa: F401
from modules.platform_admin import models as _platform_admin_models  # noqa: F401
from modules.subscriptions import models as _subscriptions_models  # noqa: F401
from modules.tenancy import models as _tenancy_models  # noqa: F401
