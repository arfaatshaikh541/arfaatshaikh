"""Correlation rules — the "detection" half of the Risk Engine.

Each rule is a pure function over one asset's `attributes` dict (as
produced by a connector's `NormalizedRecord`, see
`gridkeep_connector_sdk.base`). A rule returns an evidence dict when the
condition holds, or `None` when it doesn't — `modules.findings.engine`
decides what to do with that (create/update/auto-resolve a `Finding`),
this module only decides *whether* something is wrong.

This is a small, fixed rule registry (code, not tenant-configurable
data) — the same shape as the connector SDK's `REGISTRY`. A
tenant-configurable rules UI is a reasonable future milestone, not part
of this one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

DORMANT_ACCOUNT_THRESHOLD = timedelta(days=90)
STALE_DEVICE_THRESHOLD = timedelta(days=3)

RuleEvaluator = Callable[[dict], dict | None]


@dataclass(frozen=True)
class RuleDefinition:
    key: str
    title: str
    description: str
    category: str
    severity: str
    asset_type_key: str
    evaluate: RuleEvaluator


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _admin_without_mfa(attributes: dict) -> dict | None:
    if attributes.get("is_admin") is True and attributes.get("mfa_enabled") is False:
        return {"is_admin": True, "mfa_enabled": False}
    return None


def _dormant_user_account(attributes: dict) -> dict | None:
    last_sign_in = _parse_timestamp(attributes.get("last_sign_in_at"))
    if last_sign_in is None:
        return None
    age = datetime.now(UTC) - last_sign_in
    if age > DORMANT_ACCOUNT_THRESHOLD:
        return {"last_sign_in_at": attributes["last_sign_in_at"], "days_since_sign_in": age.days}
    return None


def _unencrypted_endpoint(attributes: dict) -> dict | None:
    if attributes.get("encrypted") is False:
        return {"encrypted": False, "os": attributes.get("os")}
    return None


def _edr_agent_unresponsive(attributes: dict) -> dict | None:
    edr_status = attributes.get("edr_status")
    if edr_status is not None and edr_status != "healthy":
        return {"edr_status": edr_status}
    return None


def _stale_device_checkin(attributes: dict) -> dict | None:
    last_seen = _parse_timestamp(attributes.get("last_seen_at"))
    if last_seen is None:
        return None
    age = datetime.now(UTC) - last_seen
    if age > STALE_DEVICE_THRESHOLD:
        return {"last_seen_at": attributes["last_seen_at"], "days_since_last_seen": age.days}
    return None


def _publicly_exposed_cloud_storage(attributes: dict) -> dict | None:
    if attributes.get("resource_type") == "storage_bucket" and attributes.get("public_access") is True:
        return {"resource_type": "storage_bucket", "public_access": True}
    return None


def _backup_job_failed(attributes: dict) -> dict | None:
    if attributes.get("last_run_status") == "failed":
        return {"last_run_status": "failed", "last_run_at": attributes.get("last_run_at")}
    return None


RULES: tuple[RuleDefinition, ...] = (
    RuleDefinition(
        key="admin_without_mfa",
        title="Administrator account without MFA",
        description="This account has administrator privileges but multi-factor authentication is "
        "not enabled.",
        category="identity",
        severity="critical",
        asset_type_key="identity_user",
        evaluate=_admin_without_mfa,
    ),
    RuleDefinition(
        key="dormant_user_account",
        title="Dormant user account",
        description="This account has not signed in for over 90 days and may be a stale credential "
        "an attacker could use unnoticed.",
        category="identity",
        severity="medium",
        asset_type_key="identity_user",
        evaluate=_dormant_user_account,
    ),
    RuleDefinition(
        key="unencrypted_endpoint",
        title="Unencrypted endpoint device",
        description="This device's disk is not encrypted, risking data exposure if it is lost or stolen.",
        category="endpoint",
        severity="high",
        asset_type_key="endpoint_device",
        evaluate=_unencrypted_endpoint,
    ),
    RuleDefinition(
        key="edr_agent_unresponsive",
        title="EDR agent unresponsive",
        description="This device's endpoint detection and response agent is not reporting healthy status.",
        category="endpoint",
        severity="high",
        asset_type_key="endpoint_device",
        evaluate=_edr_agent_unresponsive,
    ),
    RuleDefinition(
        key="stale_device_checkin",
        title="Device has not checked in recently",
        description="This device has not been seen for more than 3 days and may be lost, powered off, "
        "or offline.",
        category="endpoint",
        severity="medium",
        asset_type_key="endpoint_device",
        evaluate=_stale_device_checkin,
    ),
    RuleDefinition(
        key="publicly_exposed_cloud_storage",
        title="Publicly exposed cloud storage",
        description="This storage resource permits public access, which can expose its contents to "
        "the internet.",
        category="cloud",
        severity="critical",
        asset_type_key="cloud_resource",
        evaluate=_publicly_exposed_cloud_storage,
    ),
    RuleDefinition(
        key="backup_job_failed",
        title="Backup job failed",
        description="This backup job's most recent run failed, putting recovery at risk if data is lost.",
        category="backup",
        severity="high",
        asset_type_key="backup_job",
        evaluate=_backup_job_failed,
    ),
)

RULES_BY_ASSET_TYPE: dict[str, tuple[RuleDefinition, ...]] = {}
for _rule in RULES:
    RULES_BY_ASSET_TYPE.setdefault(_rule.asset_type_key, ())
    RULES_BY_ASSET_TYPE[_rule.asset_type_key] = (*RULES_BY_ASSET_TYPE[_rule.asset_type_key], _rule)
