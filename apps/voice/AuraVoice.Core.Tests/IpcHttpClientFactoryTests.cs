using System.Net;
using System.Net.Sockets;
using System.Text;
using AuraVoice.Core;
using Xunit;

namespace AuraVoice.Core.Tests;

/// <summary>
/// Proves IpcHttpClientFactory actually drives a real Unix domain socket
/// connection end to end -- a real listening socket accepting a real
/// connection and exchanging real HTTP/1.1 bytes, not a mock of
/// SocketsHttpHandler's internals.
/// </summary>
public class IpcHttpClientFactoryTests
{
    [Fact]
    public async Task ConnectsOverAUnixDomainSocketAndReceivesARealHttpResponse()
    {
        var socketPath = Path.Combine(Path.GetTempPath(), $"aura-voice-test-{Guid.NewGuid():N}.sock");
        if (File.Exists(socketPath))
        {
            File.Delete(socketPath);
        }

        using var listenSocket = new Socket(AddressFamily.Unix, SocketType.Stream, ProtocolType.Unspecified);
        listenSocket.Bind(new UnixDomainSocketEndPoint(socketPath));
        listenSocket.Listen(1);

        var serverTask = Task.Run(async () =>
        {
            using var connection = await listenSocket.AcceptAsync();
            var buffer = new byte[4096];
            var received = await connection.ReceiveAsync(buffer, SocketFlags.None);
            var requestText = Encoding.UTF8.GetString(buffer, 0, received);

            const string body = "{\"score\":0.9,\"detected\":true}";
            var response =
                "HTTP/1.1 200 OK\r\n" +
                "Content-Type: application/json\r\n" +
                $"Content-Length: {Encoding.UTF8.GetByteCount(body)}\r\n" +
                "Connection: close\r\n\r\n" + body;
            await connection.SendAsync(Encoding.UTF8.GetBytes(response), SocketFlags.None);
            connection.Shutdown(SocketShutdown.Both);
            return requestText;
        });

        try
        {
            using var client = IpcHttpClientFactory.CreateForSocket(socketPath);
            var response = await client.GetAsync("/voice/wake-word/check");
            var responseBody = await response.Content.ReadAsStringAsync();

            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            Assert.Contains("\"detected\":true", responseBody);

            var requestReceived = await serverTask;
            Assert.Contains("GET /voice/wake-word/check HTTP/1.1", requestReceived);
        }
        finally
        {
            listenSocket.Close();
            if (File.Exists(socketPath))
            {
                File.Delete(socketPath);
            }
        }
    }

    [Fact]
    public async Task NothingListeningOnTheSocketPathFailsRatherThanSilentlyFallingBackToTcp()
    {
        var socketPath = Path.Combine(Path.GetTempPath(), $"aura-voice-test-nolisten-{Guid.NewGuid():N}.sock");
        using var client = IpcHttpClientFactory.CreateForSocket(socketPath);

        await Assert.ThrowsAsync<HttpRequestException>(() => client.GetAsync("/health"));
    }
}
