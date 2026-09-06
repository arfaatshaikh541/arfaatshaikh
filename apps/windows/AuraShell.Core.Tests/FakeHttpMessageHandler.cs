using System.Net;

namespace AuraShell.Core.Tests;

/// <summary>
/// Routes requests by (method, path) to a canned response, recording every
/// request it saw. This is the boundary fake for these tests — real
/// AuraApiClient / ViewModel logic runs unmodified against it, only the
/// actual network call is replaced, the same principle the Python side
/// uses (an OllamaProvider pointed at an unreachable host is still real
/// code being exercised, not a mocked-out method).
/// </summary>
public sealed class FakeHttpMessageHandler : HttpMessageHandler
{
    private readonly Dictionary<(HttpMethod Method, string Path), Func<HttpRequestMessage, HttpResponseMessage>> _routes = new();

    public List<HttpRequestMessage> Requests { get; } = new();

    public void MapResponse(HttpMethod method, string path, Func<HttpRequestMessage, HttpResponseMessage> factory)
    {
        _routes[(method, path)] = factory;
    }

    public void MapJson(HttpMethod method, string path, string json, HttpStatusCode status = HttpStatusCode.OK)
    {
        MapResponse(method, path, _ => new HttpResponseMessage(status)
        {
            Content = new StringContent(json, System.Text.Encoding.UTF8, "application/json"),
        });
    }

    public void MapSseBody(string path, string sseBody)
    {
        MapResponse(HttpMethod.Post, path, _ => new HttpResponseMessage(HttpStatusCode.OK)
        {
            Content = new StringContent(sseBody, System.Text.Encoding.UTF8, "text/event-stream"),
        });
    }

    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        Requests.Add(request);
        var path = request.RequestUri!.AbsolutePath;

        if (_routes.TryGetValue((request.Method, path), out var factory))
        {
            return Task.FromResult(factory(request));
        }

        return Task.FromResult(new HttpResponseMessage(HttpStatusCode.NotFound)
        {
            Content = new StringContent($"no fake route for {request.Method} {path}"),
        });
    }
}
