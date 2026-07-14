"""Static seed catalog: modules/features, subscription plans, add-ons, and
usage metrics. This is the "commercial model" data — it defines what a
tenant can buy, not any tenant's actual data — and is meant to be edited
by the platform team (later: through the Platform Super Admin UI planned
for Milestone 9) rather than by changing application code per customer.

Convention: every module has one boolean "access" feature whose `code`
equals the module's `code` — this is what `require_module()` checks.
Additional features within a module may carry a numeric `limit`.
"""

MODULES: dict[str, dict] = {
    "account": {
        "name": "Account & Team",
        "description": "Core account and team-seat management, included with every plan.",
        "features": {
            "users": {"name": "Team members", "type": "limit"},
        },
    },
    "lead_capture": {
        "name": "Lead Capture",
        "description": "Public enquiry forms and manual lead entry.",
        "features": {"lead_capture": {"name": "Lead capture access", "type": "boolean"}},
    },
    "crm": {
        "name": "CRM Pipeline",
        "description": "Lead pipeline, notes, tags, and activity timeline.",
        "features": {
            "crm": {"name": "CRM access", "type": "boolean"},
            "leads": {"name": "Active leads", "type": "limit"},
        },
    },
    "tasks": {
        "name": "Tasks & Follow-Ups",
        "description": "Manual and automated staff tasks.",
        "features": {"tasks": {"name": "Tasks access", "type": "boolean"}},
    },
    "booking": {
        "name": "Booking",
        "description": "Consultation and callback scheduling.",
        "features": {"booking": {"name": "Booking access", "type": "boolean"}},
    },
    "workflow_automation": {
        "name": "Workflow Automation",
        "description": "Trigger-condition-action automation engine.",
        "features": {
            "workflow_automation": {"name": "Workflow automation access", "type": "boolean"},
            "automation_runs": {"name": "Automation runs / month", "type": "limit"},
        },
    },
    "proposals": {
        "name": "Proposal & Quotation Management",
        "description": "Proposal templates, line items, and acceptance.",
        "features": {"proposals": {"name": "Proposals access", "type": "boolean"}},
    },
    "client_onboarding": {
        "name": "Client Onboarding",
        "description": "Onboarding templates and cases.",
        "features": {"client_onboarding": {"name": "Client onboarding access", "type": "boolean"}},
    },
    "document_collection": {
        "name": "Secure Document Collection",
        "description": "Document requests, uploads, and approvals.",
        "features": {
            "document_collection": {"name": "Document collection access", "type": "boolean"},
            "document_storage_mb": {"name": "Document storage (MB)", "type": "limit"},
        },
    },
    "client_portal": {
        "name": "Client Portal",
        "description": "Client-facing self-service portal.",
        "features": {"client_portal": {"name": "Client portal access", "type": "boolean"}},
    },
    "deadline_tracking": {
        "name": "Compliance & Deadline Tracking",
        "description": "Recurring compliance deadlines and reminders.",
        "features": {"deadline_tracking": {"name": "Deadline tracking access", "type": "boolean"}},
    },
    "communications": {
        "name": "Communications",
        "description": "Email/notification templates and delivery logs.",
        "features": {
            "communications": {"name": "Communications access", "type": "boolean"},
            "messages": {"name": "Messages / month", "type": "limit"},
        },
    },
    "whatsapp": {
        "name": "WhatsApp Integration",
        "description": "WhatsApp Business messaging.",
        "features": {"whatsapp": {"name": "WhatsApp access", "type": "boolean"}},
    },
    "reporting": {
        "name": "Reporting",
        "description": "Operational dashboards and CSV export.",
        "features": {"reporting": {"name": "Reporting access", "type": "boolean"}},
    },
    "advanced_reporting": {
        "name": "Advanced Reporting",
        "description": "Advanced analytics and staff performance reporting.",
        "features": {"advanced_reporting": {"name": "Advanced reporting access", "type": "boolean"}},
    },
    "ai_assistant": {
        "name": "AI Assistant",
        "description": "AI-assisted drafting and summarisation.",
        "features": {
            "ai_assistant": {"name": "AI assistant access", "type": "boolean"},
            "ai_tokens": {"name": "AI tokens / month", "type": "limit"},
        },
    },
    "integrations": {
        "name": "Integrations",
        "description": "Third-party integrations and webhooks.",
        "features": {"integrations": {"name": "Integrations access", "type": "boolean"}},
    },
    "multi_branch": {
        "name": "Multi-Branch Operations",
        "description": "Multiple branch/office support.",
        "features": {
            "multi_branch": {"name": "Multi-branch access", "type": "boolean"},
            "branches": {"name": "Branches", "type": "limit"},
        },
    },
}

USAGE_METRICS: dict[str, dict] = {
    "users": {"name": "Team members", "unit": "count"},
    "leads": {"name": "Active leads", "unit": "count"},
    "document_storage_mb": {"name": "Document storage", "unit": "mb"},
    "automation_runs": {"name": "Automation runs", "unit": "count"},
    "messages": {"name": "Messages sent", "unit": "count"},
    "ai_tokens": {"name": "AI tokens", "unit": "count"},
    "branches": {"name": "Branches", "unit": "count"},
}

# config for a boolean feature: {"enabled": bool}
# config for a limit feature: {"limit": int} — key omitted/None means unlimited
PLANS: dict[str, dict] = {
    "starter": {
        "name": "Starter",
        "description": "Lead capture, CRM basics, tasks, and communications for a small team.",
        "features": {
            "users": {"limit": 5},
            "lead_capture": {"enabled": True},
            "crm": {"enabled": True},
            "leads": {"limit": 200},
            "tasks": {"enabled": True},
            "communications": {"enabled": True},
            "messages": {"limit": 500},
            "reporting": {"enabled": True},
        },
    },
    "growth": {
        "name": "Growth",
        "description": "Everything in Starter, plus booking, workflow automation, proposals, and advanced reporting.",
        "features": {
            "users": {"limit": 15},
            "lead_capture": {"enabled": True},
            "crm": {"enabled": True},
            "leads": {"limit": 1000},
            "tasks": {"enabled": True},
            "communications": {"enabled": True},
            "messages": {"limit": 2000},
            "reporting": {"enabled": True},
            "booking": {"enabled": True},
            "workflow_automation": {"enabled": True},
            "automation_runs": {"limit": 1000},
            "proposals": {"enabled": True},
            "advanced_reporting": {"enabled": True},
        },
    },
    "professional": {
        "name": "Professional",
        "description": "Everything in Growth, plus client onboarding, document collection, client portal, and deadlines.",
        "features": {
            "users": {"limit": 40},
            "lead_capture": {"enabled": True},
            "crm": {"enabled": True},
            "leads": {"limit": 5000},
            "tasks": {"enabled": True},
            "communications": {"enabled": True},
            "messages": {"limit": 10000},
            "reporting": {"enabled": True},
            "booking": {"enabled": True},
            "workflow_automation": {"enabled": True},
            "automation_runs": {"limit": 5000},
            "proposals": {"enabled": True},
            "advanced_reporting": {"enabled": True},
            "client_onboarding": {"enabled": True},
            "document_collection": {"enabled": True},
            "document_storage_mb": {"limit": 10000},
            "client_portal": {"enabled": True},
            "deadline_tracking": {"enabled": True},
        },
    },
    "enterprise": {
        "name": "Enterprise",
        "description": "All modules, multi-branch operations, WhatsApp, AI assistant, and custom limits.",
        "is_custom": False,
        "features": {
            "users": {},
            "lead_capture": {"enabled": True},
            "crm": {"enabled": True},
            "leads": {},
            "tasks": {"enabled": True},
            "communications": {"enabled": True},
            "messages": {},
            "reporting": {"enabled": True},
            "booking": {"enabled": True},
            "workflow_automation": {"enabled": True},
            "automation_runs": {},
            "proposals": {"enabled": True},
            "advanced_reporting": {"enabled": True},
            "client_onboarding": {"enabled": True},
            "document_collection": {"enabled": True},
            "document_storage_mb": {},
            "client_portal": {"enabled": True},
            "deadline_tracking": {"enabled": True},
            "multi_branch": {"enabled": True},
            "branches": {},
            "whatsapp": {"enabled": True},
            "ai_assistant": {"enabled": True},
            "ai_tokens": {"limit": 100000},
            "integrations": {"enabled": True},
        },
    },
}

ADD_ONS: dict[str, dict] = {
    "whatsapp_addon": {
        "name": "WhatsApp Integration Add-on",
        "grants": {"features": [{"feature_code": "whatsapp", "config": {"enabled": True}}]},
    },
    "extra_storage_addon": {
        "name": "Extra Document Storage Add-on",
        "grants": {
            "features": [
                {"feature_code": "document_collection", "config": {"enabled": True}},
                {"feature_code": "document_storage_mb", "config": {"limit": 50000}},
            ]
        },
    },
}
