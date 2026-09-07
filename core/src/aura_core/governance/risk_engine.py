"""Risk Engine: deterministic GREEN/AMBER/RED classification.

Per docs/architecture/04-agent-architecture.md#risk-engine: classification
is rule-based and inspectable, never a model judgment call. Unknown action
types fail safe to AMBER (never assumed GREEN), and any action carrying a
nonzero monetary amount is never classified below AMBER regardless of its
action_type.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RiskTier(str, Enum):
    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"


@dataclass
class ActionRequest:
    action_type: str
    params: dict = field(default_factory=dict)
    requested_by: str = "owner"
    amount: float | None = None
    budget_key: str | None = None


@dataclass
class RiskClassification:
    tier: RiskTier
    reason: str


# Explicit, versioned rule tables -- edit these deliberately, review like
# any other safety-relevant change. Not exhaustive; extend as new action
# types are introduced by future connectors/capabilities.
RED_ACTION_TYPES = {
    "finance.transfer_large",
    "finance.change_bank_details",
    "contract.bind",
    "personnel.hire",
    "personnel.fire",
    "security.change_root_policy",
    "credential.grant_authority",
    "identity.verify",
}

AMBER_ACTION_TYPES = {
    "finance.transfer",
    "finance.refund",
    "finance.discount",
    "finance.prepare_transaction",
    "marketing.spend",
    "deploy.production",
    "supplier.commit",
    "communication.sensitive",
    "computer_control.open_app",
    "computer_control.system_control",
    "computer_control.move_mouse",
    "computer_control.click",
    "computer_control.type_text",
    "computer_control.key_press",
    "social.publish",
    "email.send_external",
    "telephony.call",
    "http.get",
    "http.post",
    "filesystem.write_file",
    "browser.navigate",
    "browser.extract_text_multi",
    "crm.write",
    "github.comment_on_issue",
}

GREEN_ACTION_TYPES = {
    "status.read",
    "help.read",
    "tasks.read",
    "memory.read",
    "filesystem.read_file",
    "filesystem.list_dir",
    "crm.read",
    "github.list_pull_requests",
    "github.get_pull_request",
    "github.list_issues",
    "github.get_issue",
    "github.get_combined_status",
    "email.list_messages",
    "email.get_message",
    "email.search_messages",
}


class RiskEngine:
    def classify(self, request: ActionRequest) -> RiskClassification:
        action_type = request.action_type

        if action_type in RED_ACTION_TYPES:
            return RiskClassification(RiskTier.RED, f"'{action_type}' is on the RED action-type list")

        if request.amount is not None and request.amount > 0 and action_type not in GREEN_ACTION_TYPES:
            return RiskClassification(RiskTier.AMBER, "action carries a nonzero monetary amount")

        if action_type in AMBER_ACTION_TYPES:
            return RiskClassification(RiskTier.AMBER, f"'{action_type}' is on the AMBER action-type list")

        if action_type in GREEN_ACTION_TYPES:
            return RiskClassification(RiskTier.GREEN, f"'{action_type}' is on the GREEN action-type list")

        return RiskClassification(
            RiskTier.AMBER,
            f"unrecognized action_type '{action_type}'; failing safe to AMBER pending explicit classification",
        )
