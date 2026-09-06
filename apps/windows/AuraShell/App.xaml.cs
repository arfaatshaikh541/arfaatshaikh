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
        // — run it with `uvicorn aura_core.api:create_app --factory` per
        // core/RUNBOOK.md. This shell is a thin client over its HTTP API;
        // it holds no memory, policy, or governance state of its own.
        var baseUrl = Environment.GetEnvironmentVariable("AURA_CORE_URL") ?? "http://localhost:8000";
        var httpClient = new HttpClient { BaseAddress = new Uri(baseUrl) };
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
