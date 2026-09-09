using System.Net.Http;
using System.Windows;
using AuraShell.Core;

namespace AuraShell;

public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        // The core runtime (core/src/aura_core/api) is a separate process
        // — run it with `aura serve` per core/RUNBOOK.md. This shell is a
        // thin client over its HTTP API; it holds no memory, policy, or
        // governance state of its own.
        //
        // AURA_CORE_SOCKET (a Unix domain socket path, printed by `aura
        // serve` on startup) is the section-7 "local, not localhost"
        // transport and takes priority when set. AURA_CORE_URL is the
        // loopback-TCP fallback for tooling that only speaks HTTP-over-TCP
        // -- `aura serve --host`.
        // AURA_DEVICE_TOKEN (saved by `aura enroll`) is attached to every
        // request once set -- once an owner enrolls, every mutating
        // endpoint requires it, so this shell keeps working uninterrupted
        // rather than starting to get 401s on the day enrollment happens.
        var socketPath = Environment.GetEnvironmentVariable("AURA_CORE_SOCKET");
        var deviceToken = Environment.GetEnvironmentVariable("AURA_DEVICE_TOKEN");
        HttpClient httpClient;
        if (socketPath is not null)
        {
            httpClient = IpcHttpClientFactory.CreateForSocket(socketPath, deviceToken);
        }
        else
        {
            httpClient = new HttpClient { BaseAddress = new Uri(Environment.GetEnvironmentVariable("AURA_CORE_URL") ?? "http://localhost:8000") };
            DeviceTokenHeader.AttachIfConfigured(httpClient, deviceToken);
        }
        var apiClient = new AuraApiClient(httpClient);
        var shell = new InterfaceShellViewModel(apiClient);

        // The ONLY window this application ever creates, and MainWindow is
        // no longer a fixed Chat/Status/Approvals dashboard: its content
        // is driven entirely by shell.Mode, which always starts at
        // Booting (see InterfaceModeManager) and can only reach
        // BackendMode through a real authenticated hotkey challenge. A
        // crash or restart re-enters at exactly this same line and
        // replays the full boot sequence -- there is no "resume last
        // mode" path anywhere in this application, by construction.
        var window = new MainWindow(shell, apiClient);
        window.Show();

        // Fire-and-forget on purpose: the window is already visible and
        // responsive. If aura_core isn't reachable yet, StartAsync's own
        // try/catch reports that honestly on the authentication screen
        // rather than crashing startup or hanging behind a blocking
        // spinner.
        _ = window.RunStartupSequenceAsync();
    }
}
