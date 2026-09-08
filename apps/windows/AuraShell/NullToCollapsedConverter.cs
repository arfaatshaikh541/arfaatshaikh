using System.Globalization;
using System.Windows;
using System.Windows.Data;

namespace AuraShell;

/// <summary>Visible when bound value is null, Collapsed otherwise -- used
/// for BackendModeView's "no diagnostics loaded yet" placeholder, which
/// must disappear the moment real data (never fabricated) has actually
/// been fetched.</summary>
public sealed class NullToCollapsedConverter : IValueConverter
{
    public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture) =>
        value is null ? Visibility.Visible : Visibility.Collapsed;

    public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture) =>
        throw new NotSupportedException();
}
