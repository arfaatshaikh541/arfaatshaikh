using System.Globalization;
using System.IO;
using System.Windows.Data;
using System.Windows.Media.Imaging;

namespace AuraShell;

/// <summary>Decodes a base64-encoded PNG (the "Add Device" pairing QR --
/// see aura_core.identity.qr and InterfaceShellViewModel.PairingQrPngBase64)
/// into a real, displayable BitmapImage. Returns null for anything that
/// isn't valid, decodable image data -- a malformed or missing QR must
/// show nothing, never a broken-image icon or a crash.</summary>
public sealed class Base64ToBitmapImageConverter : IValueConverter
{
    public object? Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
    {
        if (value is not string base64 || string.IsNullOrWhiteSpace(base64))
        {
            return null;
        }
        try
        {
            var bytes = System.Convert.FromBase64String(base64);
            var image = new BitmapImage();
            using var stream = new MemoryStream(bytes);
            image.BeginInit();
            image.CacheOption = BitmapCacheOption.OnLoad;
            image.StreamSource = stream;
            image.EndInit();
            image.Freeze();
            return image;
        }
        catch (FormatException)
        {
            return null;
        }
        catch (NotSupportedException)
        {
            // Thrown by BitmapImage for bytes that decode from base64
            // fine but aren't a real, decodable image.
            return null;
        }
    }

    public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture) =>
        throw new NotSupportedException();
}
