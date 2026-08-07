using Avalonia.Collections;
using Avalonia.Styling;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Material.Icons;
using AristeusUI.Enums;
using AristeusUI.Models;

namespace AristeusUI.Demo.Features.Theming;

public partial class ThemingViewModel : DemoPageBase
{
    public Action<AristeusBackgroundStyle>? BackgroundStyleChanged { get; set; }
    public Action<bool>? BackgroundAnimationsChanged { get; set; }
    public Action<bool>? BackgroundTransitionsChanged { get; set; }
    public Action<string?>? CustomBackgroundStyleChanged { get; set; }
    
    public IAvaloniaReadOnlyList<AristeusColorTheme> AvailableColors { get; }
    public IAvaloniaReadOnlyList<AristeusBackgroundStyle> AvailableBackgroundStyles { get; }
    public IAvaloniaReadOnlyList<string> CustomShaders { get; } = new AvaloniaList<string> { "Space", "Weird", "Clouds" };

    private readonly AristeusTheme _theme = AristeusTheme.GetInstance();

    [ObservableProperty] private bool _isLightTheme;
    [ObservableProperty] private AristeusBackgroundStyle _backgroundStyle;
    [ObservableProperty] private bool _backgroundAnimations;
    [ObservableProperty] private bool _backgroundTransitions;
    [ObservableProperty] private string _themingHeader = "Base Theme";

    private string? _customShader = null;
    
    public ThemingViewModel() : base("Theming", MaterialIconKind.PaletteOutline, -200)
    {
        AvailableBackgroundStyles = new AvaloniaList<AristeusBackgroundStyle>(Enum.GetValues<AristeusBackgroundStyle>());
        AvailableColors = _theme.ColorThemes;
        IsLightTheme = _theme.ActiveBaseTheme == ThemeVariant.Light;
        _theme.OnBaseThemeChanged += variant => {
            IsLightTheme = variant == ThemeVariant.Light;
        };
        _theme.OnColorThemeChanged += theme => {
            // TODO: Implement a way to make this correct, might need to wrap the thing in a VM, this isn't ideal.
        };
    }

    partial void OnIsLightThemeChanged(bool value) =>
        _theme.ChangeBaseTheme(value ? ThemeVariant.Light : ThemeVariant.Dark);
    
    [RelayCommand]
    private void SwitchToColorTheme(AristeusColorTheme colorTheme) =>
        _theme.ChangeColorTheme(colorTheme);

    partial void OnBackgroundStyleChanged(AristeusBackgroundStyle value) => 
        BackgroundStyleChanged?.Invoke(value);

    partial void OnBackgroundAnimationsChanged(bool value) => 
        BackgroundAnimationsChanged?.Invoke(value);

    partial void OnBackgroundTransitionsChanged(bool value) =>
        BackgroundTransitionsChanged?.Invoke(value);

    [RelayCommand]
    private void TryCustomShader(string shaderType)
    {
        _customShader = _customShader == shaderType ? null : shaderType;
        CustomBackgroundStyleChanged?.Invoke(_customShader);
    }
}