using System.Globalization;
using System.Windows.Data;

namespace AuraShell;

public sealed class BoolToKillSwitchLabelConverter : IValueConverter
{
    public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture) =>
        value is true ? "Disengage kill switch" : "Engage kill switch";

    public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture) =>
        throw new NotSupportedException();
}
