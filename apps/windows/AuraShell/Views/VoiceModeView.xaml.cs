using System.ComponentModel;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using AuraShell.Core;

namespace AuraShell.Views;

public partial class VoiceModeView : UserControl
{
    public VoiceModeView()
    {
        InitializeComponent();
        DataContextChanged += OnDataContextChanged;
    }

    private void OnDataContextChanged(object sender, DependencyPropertyChangedEventArgs e)
    {
        if (e.OldValue is VoiceModeViewModel oldVm)
        {
            oldVm.PropertyChanged -= OnPropertyChanged;
        }
        if (e.NewValue is VoiceModeViewModel newVm)
        {
            newVm.PropertyChanged += OnPropertyChanged;
            Refresh(newVm);
        }
    }

    private void OnPropertyChanged(object? sender, PropertyChangedEventArgs e) =>
        Dispatcher.Invoke(() => Refresh((VoiceModeViewModel)sender!));

    private void Refresh(VoiceModeViewModel vm)
    {
        var (color, label) = vm.State switch
        {
            VoiceVisualState.Idle => (Colors.Gray, "Idle"),
            VoiceVisualState.ListeningForWake => (Color.FromRgb(0x3A, 0x6E, 0xA5), "Listening"),
            VoiceVisualState.Awake => (Color.FromRgb(0x4C, 0xAF, 0x50), "Awake"),
            VoiceVisualState.Processing => (Color.FromRgb(0xE0, 0xA8, 0x00), "Thinking"),
            VoiceVisualState.Speaking => (Color.FromRgb(0x64, 0xB5, 0xF6), "Speaking"),
            VoiceVisualState.Muted => (Color.FromRgb(0x9E, 0x9E, 0x9E), "Muted"),
            VoiceVisualState.Offline => (Color.FromRgb(0xB0, 0x00, 0x20), "Offline"),
            _ => (Colors.DimGray, "Connecting…"),
        };

        Orb.Fill = new SolidColorBrush(color);
        OrbGlow.Color = color;
        StateText.Text = label;
        MuteToggle.IsChecked = vm.IsMuted;
    }

    private void OnMuteChecked(object sender, RoutedEventArgs e) =>
        (DataContext as VoiceModeViewModel)?.SetMuted(true);

    private void OnMuteUnchecked(object sender, RoutedEventArgs e) =>
        (DataContext as VoiceModeViewModel)?.SetMuted(false);
}
