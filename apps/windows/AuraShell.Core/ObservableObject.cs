using System.ComponentModel;
using System.Runtime.CompilerServices;

namespace AuraShell.Core;

/// <summary>Minimal INotifyPropertyChanged base, hand-rolled for the same
/// reason as RelayCommand: no external MVVM package dependency.</summary>
public abstract class ObservableObject : INotifyPropertyChanged
{
    public event PropertyChangedEventHandler? PropertyChanged;

    protected bool SetProperty<T>(ref T field, T value, [CallerMemberName] string? propertyName = null)
    {
        if (EqualityComparer<T>.Default.Equals(field, value))
        {
            return false;
        }

        field = value;
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
        return true;
    }
}
