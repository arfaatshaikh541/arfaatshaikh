using System.Text.Json.Serialization;

namespace AuraShell.Core;

/// <summary>
/// One event from the AURA core's /chat Server-Sent-Events stream. Field
/// names mirror the {"event": ..., "data": ...} JSON written by
/// core/src/aura_core/api/app.py's _sse() helper exactly — this is a
/// contract between the two, not an independent guess.
/// </summary>
public sealed record ChatEvent(
    [property: JsonPropertyName("event")] string Event,
    [property: JsonPropertyName("data")] string Data);

public sealed record CapabilityInfo(
    [property: JsonPropertyName("status")] string Status,
    [property: JsonPropertyName("detail")] string Detail,
    [property: JsonPropertyName("checked_at")] string CheckedAt);

public sealed record ApprovalInfo(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("action_type")] string ActionType,
    [property: JsonPropertyName("risk_tier")] string RiskTier,
    [property: JsonPropertyName("reason")] string Reason,
    [property: JsonPropertyName("status")] string Status,
    [property: JsonPropertyName("created_at")] string CreatedAt);

public sealed record AuditEntryInfo(
    [property: JsonPropertyName("seq")] long Seq,
    [property: JsonPropertyName("timestamp")] string Timestamp,
    [property: JsonPropertyName("actor")] string Actor,
    [property: JsonPropertyName("action_type")] string ActionType,
    [property: JsonPropertyName("risk_tier")] string RiskTier,
    [property: JsonPropertyName("decision")] string Decision,
    [property: JsonPropertyName("approval_id")] string? ApprovalId,
    [property: JsonPropertyName("result_status")] string ResultStatus,
    [property: JsonPropertyName("result_message")] string ResultMessage);

public sealed record AuditVerification(
    [property: JsonPropertyName("valid")] bool Valid,
    [property: JsonPropertyName("broken_at_seq")] long? BrokenAtSeq,
    [property: JsonPropertyName("entries_checked")] int EntriesChecked);

public sealed record ApprovalDecisionResult(
    [property: JsonPropertyName("status")] string Status,
    [property: JsonPropertyName("message")] string Message);

public sealed record VoiceStateInfo(
    [property: JsonPropertyName("state")] string State,
    [property: JsonPropertyName("reported_at")] string? ReportedAt);

public sealed record InterfaceConfig(
    [property: JsonPropertyName("default_interface_mode")] string DefaultInterfaceMode,
    [property: JsonPropertyName("backend_toggle_hotkey")] string BackendToggleHotkey,
    [property: JsonPropertyName("require_backend_reauth")] bool RequireBackendReauth,
    [property: JsonPropertyName("backend_elevation_ttl_seconds")] int BackendElevationTtlSeconds);

public sealed record BackendAuthResult(
    [property: JsonPropertyName("elevation_token")] string ElevationToken,
    [property: JsonPropertyName("expires_in_seconds")] double ExpiresInSeconds);

public sealed record BackendSessionStatus(
    [property: JsonPropertyName("active")] bool Active,
    [property: JsonPropertyName("seconds_remaining")] double SecondsRemaining);

/// <summary>
/// The real substitute this build has for a production startup
/// authentication screen (no Windows Hello / hardware-backed factor is
/// wired up): reports whether the calling device already carries a
/// valid, trusted device token. See core/src/aura_core/api/app.py's
/// /identity/whoami.
/// </summary>
public sealed record WhoAmIInfo(
    [property: JsonPropertyName("enrolled")] bool Enrolled,
    [property: JsonPropertyName("owner_name")] string? OwnerName,
    [property: JsonPropertyName("device_label")] string? DeviceLabel);

/// <summary>
/// Real system state pulled from diagnostics/health.py's collect_diagnostics
/// (see /backend/diagnostics) -- never fabricated demo data. RecentGuardianEvents
/// and CapabilityStatus are kept as raw JsonElement rather than modeled
/// record shapes: their exact structure is owned by the Security Guardian
/// and the status registry respectively, and re-typing them here would
/// risk silently dropping fields Backend Mode should still show honestly.
/// </summary>
public sealed record BackendDiagnostics(
    [property: JsonPropertyName("audit_chain_valid")] bool AuditChainValid,
    [property: JsonPropertyName("audit_entries_checked")] int AuditEntriesChecked,
    [property: JsonPropertyName("recent_guardian_events")] System.Text.Json.JsonElement RecentGuardianEvents,
    [property: JsonPropertyName("capability_status")] System.Text.Json.JsonElement CapabilityStatus);
