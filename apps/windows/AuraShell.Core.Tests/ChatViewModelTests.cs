using AuraShell.Core;
using Xunit;

namespace AuraShell.Core.Tests;

public class ChatViewModelTests
{
    [Fact]
    public async Task SendAsync_appends_the_user_line_then_builds_the_response_incrementally()
    {
        var handler = new FakeHttpMessageHandler();
        handler.MapSseBody("/chat",
            "data: {\"event\": \"lane\", \"data\": \"deterministic\"}\n\n" +
            "data: {\"event\": \"chunk\", \"data\": \"memory.store: LIVE\"}\n\n" +
            "data: {\"event\": \"done\", \"data\": \"EXECUTED\"}\n\n");
        var client = new AuraApiClient(new HttpClient(handler) { BaseAddress = new Uri("http://fake.local") });
        var viewModel = new ChatViewModel(client);

        viewModel.InputText = "status";
        await viewModel.SendAsync();

        Assert.Equal("you> status", viewModel.Transcript[0]);
        Assert.Equal("aura [deterministic]> memory.store: LIVE", viewModel.Transcript[1]);
        Assert.Equal("EXECUTED", viewModel.LastOutcomeStatus);
        Assert.Equal(string.Empty, viewModel.InputText); // cleared after send
    }

    [Fact]
    public async Task SendAsync_does_nothing_for_blank_input()
    {
        var handler = new FakeHttpMessageHandler(); // no routes mapped -- a call would 404 and throw
        var client = new AuraApiClient(new HttpClient(handler) { BaseAddress = new Uri("http://fake.local") });
        var viewModel = new ChatViewModel(client);

        viewModel.InputText = "   ";
        await viewModel.SendAsync();

        Assert.Empty(viewModel.Transcript);
        Assert.Empty(handler.Requests);
    }

    [Fact]
    public void SendCommand_CanExecute_is_false_until_input_is_non_blank()
    {
        var client = new AuraApiClient(new HttpClient(new FakeHttpMessageHandler()) { BaseAddress = new Uri("http://fake.local") });
        var viewModel = new ChatViewModel(client);

        Assert.False(viewModel.SendCommand.CanExecute(null));

        viewModel.InputText = "hello";

        Assert.True(viewModel.SendCommand.CanExecute(null));
    }
}
