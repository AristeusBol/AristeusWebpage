using Avalonia.Media;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using AristeusUI.Controls;
using AristeusUI.Dialogs;
using AristeusUI.Models;

namespace AristeusUI.Demo.Features.CustomTheme;

public partial class CustomThemeDialogViewModel(AristeusTheme theme, IAristeusDialog dialog) : ObservableObject
{
    [ObservableProperty] private string _displayName = "Pink";
    [ObservableProperty] private Color _primaryColor = Colors.DeepPink;
    [ObservableProperty] private Color _accentColor = Colors.Pink;

    [RelayCommand]
    private void TryCreateTheme()
    {
        if (string.IsNullOrEmpty(DisplayName)) return;
        var theme1 = new AristeusColorTheme(DisplayName, PrimaryColor, AccentColor);
        theme.AddColorTheme(theme1);
        theme.ChangeColorTheme(theme1);
        dialog.Dismiss();
    }
}