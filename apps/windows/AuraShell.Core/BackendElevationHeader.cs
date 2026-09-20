namespace AuraShell.Core;

/// <summary>
/// The header name the core API's require_backend_elevation dependency
/// checks (aura_core/api/app.py) on every /backend/* endpoint, beyond
/// the ordinary device-trust header. Deliberately NOT a default header
/// set once on the HttpClient the way DeviceTokenHeader is: an
/// elevation token is short-lived and only valid while Backend Mode is
/// open, so it is attached per-request by InterfaceModeManager's
/// caller, never left sitting as ambient state on a long-lived client
/// that also serves ordinary Voice Mode requests.
/// </summary>
public static class BackendElevationHeader
{
    public const string Name = "X-Aura-Backend-Elevation";
}
