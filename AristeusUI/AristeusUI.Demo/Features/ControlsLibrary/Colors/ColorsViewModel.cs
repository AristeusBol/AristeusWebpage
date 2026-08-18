using System.Collections.Generic;
using System.Linq;
using Avalonia;
using Avalonia.Collections;
using Avalonia.Controls;
using Avalonia.Media;
using Avalonia.Styling;
using CommunityToolkit.Mvvm.Input;
using Material.Icons;
using AristeusUI.Demo.Services;
using AristeusUI.Models;
using AristeusUI.Toasts;

namespace AristeusUI.Demo.Features.ControlsLibrary.Colors;

public partial class ColorsViewModel : DemoPageBase
{
    public AvaloniaList<ColorViewModel> Colors { get; } = [];

    private readonly Dictionary<ThemeVariant, Dictionary<string, IBrush>> _baseThemeCache = new();
    private readonly Dictionary<AristeusColorTheme, Dictionary<string, IBrush>> _colorThemeCache = new();

    private readonly ClipboardService _clipboardService;
    private readonly IAristeusToastManager _toastManager;

    public ColorsViewModel(ClipboardService clipboardService, IAristeusToastManager toastManager) : base("Colors", MaterialIconKind.Paintbrush)
    {
        _clipboardService = clipboardService;
        _toastManager = toastManager;
        
        var aristeusTheme = AristeusTheme.GetInstance();

        Colors.AddRange(BuildOrGetColorTheme(aristeusTheme.ActiveColorTheme!)
            .Select(x => new ColorViewModel(x.Key, x.Value)));
        Colors.AddRange(BuildOrGetBaseTheme(aristeusTheme.ActiveBaseTheme)
            .OrderBy(x => x.Key)
            .Select(x => new ColorViewModel(x.Key, x.Value)));

        aristeusTheme.OnBaseThemeChanged += variant => ReApply(aristeusTheme.ActiveColorTheme!, variant);
        aristeusTheme.OnColorThemeChanged += theme => ReApply(theme, aristeusTheme.ActiveBaseTheme);
    }

    private void ReApply(AristeusColorTheme theme, ThemeVariant variant)
    {
        var themeBrushes = BuildOrGetColorTheme(theme);
        var baseBrushes = BuildOrGetBaseTheme(variant);
        foreach (var vm in Colors)
        {
            if (themeBrushes.TryGetValue(vm.Name, out var themeBrush))
                vm.Brush = themeBrush;
            else if (baseBrushes.TryGetValue(vm.Name, out var baseBrush))
                vm.Brush = baseBrush;
        }
    }

    private Dictionary<string, IBrush> BuildOrGetColorTheme(AristeusColorTheme theme)
    {
        if (_colorThemeCache.TryGetValue(theme, out var res))
            return res;
        var colors = Application.Current.Resources
            .Where(x => x.Value is Color)
            .ToDictionary(x => (string)x.Key, y => (IBrush)new SolidColorBrush((Color)y.Value));
        _colorThemeCache[theme] = colors;
        return _colorThemeCache[theme];
    }

    private Dictionary<string, IBrush> BuildOrGetBaseTheme(ThemeVariant variant)
    {
        if (_baseThemeCache.TryGetValue(variant, out var res))
            return res;
        var themeVariantResources = (ResourceDictionary)AristeusTheme.GetInstance().Resources.ThemeDictionaries[variant];
        var brushes = themeVariantResources
            .Where(x => x.Value is Color)
            .ToDictionary(x => (string)x.Key, y => (IBrush)new SolidColorBrush((Color)y.Value!));

        _baseThemeCache[variant] = brushes;
        return _baseThemeCache[variant];
    }

    [RelayCommand]
    private void OnColorClicked(ColorViewModel color)
    {
        _clipboardService.CopyToClipboard(color.Name);
        _toastManager.CreateSimpleInfoToast()
            .WithTitle("Color Copied To Clipboard")
            .WithContent($"Copied the name of {color.Name} to your clipboard.")
            .Queue();
    }
}