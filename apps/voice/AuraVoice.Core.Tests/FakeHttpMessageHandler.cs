using System.Net;

namespace AuraVoice.Core.Tests;

/// <summary>Same pattern as AuraShell.Core.Tests' fake: routes requests
/// by (method, path) to a canned response, recording every request seen,
/// so real client logic runs against a real-shaped HTTP layer.</summary>
public sealed class FakeHttpMessageHandler : HttpMessageHandler
{
    private readonly Dictionary<(HttpMethod Method, string Path), Func<HttpRequestMessage, HttpResponseMessage>> _routes = new();

    public List<HttpRequestMessage> Requests { get; } = new();
    public List<string> RequestBodies { get; } = new();

    public void MapJson(HttpMethod method, string path, string json, HttpStatusCode status = HttpStatusCode.OK)
    {
        _routes[(method, path)] = _ => new HttpResponseMessage(status)
        {
            Content = new StringContent(json, System.Text.Encoding.UTF8, "application/json"),
        };
    }

    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        Requests.Add(request);
        if (request.Content is not null)
        {
            RequestBodies.Add(request.Content.ReadAsStringAsync(cancellationToken).GetAwaiter().GetResult());
        }

        var path = request.RequestUri!.AbsolutePath;
        if (_routes.TryGetValue((request.Method, path), out var factory))
        {
            return Task.FromResult(factory(request));
        }

        return Task.FromResult(new HttpResponseMessage(HttpStatusCode.NotFound));
    }
}
