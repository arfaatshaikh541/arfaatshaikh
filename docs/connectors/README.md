# Connector Framework

## Purpose

A connector is the only way any agent reaches an external system. Connectors are
built once, reviewed, and reused — agents never construct ad hoc API calls to
arbitrary external services.

## Candidate integrations

Email, calendars, contacts, CRM, social media, advertising platforms, analytics,
websites, GitHub, cloud infrastructure, support platforms, accounting, invoicing,
payments, document systems, conferencing, messaging, SEO platforms, project management.

## Every connector requires

- **Explicit owner authorization** — a connector cannot be added and start being used
  by an agent without the owner completing an explicit auth flow (OAuth consent, API
  key entry into the vault, etc.) through the Control Plane. No agent can self-provision
  a new connector.
- **Minimal permissions** — request the narrowest OAuth scope / API permission that
  satisfies the declared use case (e.g., a "read calendar for scheduling" connector does
  not also request contact-deletion rights just because the provider bundles them).
- **Credential isolation** — the connector's long-lived secret (OAuth refresh token, API
  key) lives only in the Credential Broker/vault; agents receive short-lived scoped
  tokens per the flow in `04-agent-architecture.md`.
- **Rate limiting** — connector-specific rate limits, both to respect the third party's
  terms of service and to bound damage from a runaway agent loop.
- **Audit** — every connector call is logged through the Action Broker like any other
  action (who, what, when, result).
- **Health checks** — connectors are monitored for auth expiry, elevated error rates,
  and schema drift (the third party changed their API), alerting before a silent
  failure cascades into missed business events.
- **Revocation** — the owner can revoke a connector's access instantly from the Control
  Plane; revocation immediately invalidates any outstanding scoped tokens derived from
  it.

## Connector manifest

Each connector is registered with a signed manifest declaring: provider, auth method,
scopes requested, data classes it can read/write, rate limits, and the specific
capabilities (tool calls) it exposes to agents. The manifest is what the Action Broker
validates tool calls against — an agent cannot invoke a capability the connector's
manifest doesn't declare, even if it hallucinates one.

## New connector = supply-chain event

Adding a new connector (or a new MCP-server-based tool) goes through the same review
described in `docs/security/README.md#supply-chain-security`: who maintains it, what
it requests, what data it touches, before it's approved for use — because a connector
is effectively a grant of tool-calling trust into a third-party system.
