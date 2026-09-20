using AuraShell.Core;
using Xunit;

namespace AuraShell.Core.Tests;

public class DeviceTokenHeaderTests
{
    [Fact]
    public void AttachesTheHeaderWhenATokenIsGiven()
    {
        using var client = new HttpClient();

        DeviceTokenHeader.AttachIfConfigured(client, "the-real-token");

        Assert.True(client.DefaultRequestHeaders.Contains(DeviceTokenHeader.Name));
        Assert.Equal("the-real-token", client.DefaultRequestHeaders.GetValues(DeviceTokenHeader.Name).Single());
    }

    [Fact]
    public void DoesNothingWhenTheTokenIsNull()
    {
        using var client = new HttpClient();

        DeviceTokenHeader.AttachIfConfigured(client, null);

        Assert.False(client.DefaultRequestHeaders.Contains(DeviceTokenHeader.Name));
    }

    [Fact]
    public void DoesNothingWhenTheTokenIsEmpty()
    {
        using var client = new HttpClient();

        DeviceTokenHeader.AttachIfConfigured(client, string.Empty);

        Assert.False(client.DefaultRequestHeaders.Contains(DeviceTokenHeader.Name));
    }
}
