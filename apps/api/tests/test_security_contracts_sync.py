"""Guards against the TypeScript and Python security-contracts vocabularies
drifting apart (see core/security_contracts.py and
packages/security-contracts/src/index.ts docstrings). Parses the TS
source as text rather than executing it — this test has no Node
dependency, so it runs in the same pytest process as everything else."""

from __future__ import annotations

import re
from pathlib import Path

from core.security_contracts import (
    AUTOMATION_MODES,
    MODULES,
    PERMISSIONS,
    PLATFORM_ROLES,
    TENANT_ROLES,
    TENANT_STATUSES,
)

_TS_SOURCE = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "security-contracts"
    / "src"
    / "index.ts"
).read_text()


def _extract_ts_array(const_name: str) -> list[str | int]:
    match = re.search(rf"export const {const_name} = \[(.*?)\] as const;", _TS_SOURCE, re.DOTALL)
    assert match, f"Could not find `{const_name}` in the TypeScript security contracts source."
    body = match.group(1)
    string_items = re.findall(r'"([^"]+)"', body)
    if string_items:
        return string_items
    return [int(n) for n in re.findall(r"-?\d+", body)]


def test_permissions_match():
    assert _extract_ts_array("PERMISSIONS") == list(PERMISSIONS)


def test_tenant_roles_match():
    assert _extract_ts_array("TENANT_ROLES") == list(TENANT_ROLES)


def test_platform_roles_match():
    assert _extract_ts_array("PLATFORM_ROLES") == list(PLATFORM_ROLES)


def test_tenant_statuses_match():
    assert _extract_ts_array("TENANT_STATUSES") == list(TENANT_STATUSES)


def test_modules_match():
    assert _extract_ts_array("MODULES") == list(MODULES)


def test_automation_modes_match():
    assert _extract_ts_array("AUTOMATION_MODES") == list(AUTOMATION_MODES)
