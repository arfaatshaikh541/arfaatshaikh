using System.Net.Sockets;

namespace AuraShell.Core;

/// <summary>
/// Builds an HttpClient that talks to the AURA core API over a Unix
/// domain socket instead of loopback TCP -- section 7's "local, not
/// localhost" transport. Windows has shipped native AF_UNIX support
/// since Windows 10 build 17063 (GA since version 1809 / Windows Server
/// 2019) and .NET's UnixDomainSocketEndPoint has worked there since .NET
/// Core 3.0, so this same code path runs unmodified on both platforms --
/// see core/src/aura_core/ipc.py's module docstring for the full
/// rationale. Everything above the transport (AuraApiClient's request/
/// response/SSE-parsing code) is completely unaware this isn't a normal
/// TCP connection.
/// </summary>
public static class IpcHttpClientFactory
{
    /// <summary>
    /// The base address is a syntactic placeholder -- ConnectCallback
    /// intercepts the actual connection before any DNS/TCP resolution of
    /// this host would ever happen, so its value is never used to route
    /// anywhere. It must be a well-formed absolute URI purely because
    /// HttpClient requires one to build relative-path requests against.
    /// </summary>
    public static HttpClient CreateForSocket(string socketPath)
    {
        var handler = new SocketsHttpHandler
        {
            ConnectCallback = async (_, cancellationToken) =>
            {
                var endpoint = new UnixDomainSocketEndPoint(socketPath);
                var socket = new Socket(AddressFamily.Unix, SocketType.Stream, ProtocolType.Unspecified);
                try
                {
                    await socket.ConnectAsync(endpoint, cancellationToken);
                    return new NetworkStream(socket, ownsSocket: true);
                }
                catch
                {
                    socket.Dispose();
                    throw;
                }
            },
        };

        return new HttpClient(handler) { BaseAddress = new Uri("http://aura-core.ipc") };
    }
}
