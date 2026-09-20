namespace AuraShell.Core;

/// <summary>
/// The header name the core API's device-trust gate checks
/// (aura_core/api/app.py's require_device_token dependency) on every
/// mutating endpoint once an owner has enrolled. Centralized here so the
/// IPC and TCP client construction paths -- and AuraVoice.Windows.Host,
/// which references this assembly -- never risk drifting on the literal
/// string.
/// </summary>
public static class DeviceTokenHeader
{
    public const string Name = "X-Aura-Device-Token";

    /// <summary>
    /// No-op when <paramref name="deviceToken"/> is null or empty -- an
    /// installation that hasn't run `aura enroll` yet has no token to
    /// send, and every endpoint stays open exactly as before until it
    /// does, matching the server-side gate's own before/after-enrollment
    /// behavior.
    /// </summary>
    public static void AttachIfConfigured(HttpClient client, string? deviceToken)
    {
        if (!string.IsNullOrEmpty(deviceToken))
        {
            client.DefaultRequestHeaders.Add(Name, deviceToken);
        }
    }
}
