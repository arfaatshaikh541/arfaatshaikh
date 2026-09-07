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
        var viewModel = new MainViewModel(apiClient);

        var window = new MainWindow(viewModel);
        window.Show();

        // Fire-and-forget on purpose: the window is already visible and
        // responsive (per the "immediate acknowledgement, not a blocking
        // spinner" requirement). If the core server isn't running yet,
        // this fails quietly and the Status tab shows the honest
        // NOT_CONNECTED/UNAVAILABLE state instead of crashing startup.
        _ = viewModel.InitializeAsync();
    }
}
