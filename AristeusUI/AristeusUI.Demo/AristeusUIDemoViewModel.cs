using Avalonia.Collections;
using Avalonia.Styling;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using AristeusUI.Controls;
using AristeusUI.Demo.Features;
using AristeusUI.Demo.Features.CustomTheme;
using AristeusUI.Demo.Services;
using AristeusUI.Demo.Utilities;
using AristeusUI.Models;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Media;
using AristeusUI.Demo.Features.ControlsLibrary.Dialogs;
using AristeusUI.Demo.Features.Theming;
using AristeusUI.Dialogs;
using AristeusUI.Enums;
using AristeusUI.Theme.Shadcn;
using AristeusUI.Toasts;

namespace AristeusUI.Demo;

public partial class AristeusUIDemoViewModel : ObservableObject
{
    public IAvaloniaReadOnlyList<DemoPageBase> DemoPages { get; }
    public PageNavigationService PageNavigationService { get; }

    public IAvaloniaReadOnlyList<AristeusColorTheme> Themes { get; }

    public IAvaloniaReadOnlyList<AristeusBackgroundStyle> BackgroundStyles { get; }

    public IAristeusToastManager ToastManager { get; }
    public IAristeusDialogManager DialogManager { get; }

    [ObservableProperty] private ThemeVariant _baseTheme;
    [ObservableProperty] private DemoPageBase? _activePage;
    [ObservableProperty] private bool _windowLocked;
    [ObservableProperty] private bool _titleBarVisible = true;
    [ObservableProperty] private AristeusBackgroundStyle _backgroundStyle = AristeusBackgroundStyle.GradientSoft;
    [ObservableProperty] private bool _animationsEnabled;
    [ObservableProperty] private string? _customShaderFile;
    [ObservableProperty] private bool _transitionsEnabled;
    [ObservableProperty] private double _transitionTime;

    [ObservableProperty] private bool _showTitleBar = true;
    [ObservableProperty] private bool _showBottomBar = true;

    private readonly AristeusTheme _theme;
    private readonly ThemingViewModel _theming;

    public AristeusUIDemoViewModel(IEnumerable<DemoPageBase> demoPages, PageNavigationService pageNavigationService, IAristeusToastManager toastManager, IAristeusDialogManager dialogManager)
    {
        ToastManager = toastManager;
        DialogManager = dialogManager;
        DemoPages = new AvaloniaList<DemoPageBase>(demoPages.OrderBy(x => x.Index).ThenBy(x => x.DisplayName));
        PageNavigationService = pageNavigationService;
        _theming = (ThemingViewModel)DemoPages.First(x => x is ThemingViewModel);
        _theming.BackgroundStyleChanged += style => BackgroundStyle = style;
        _theming.BackgroundAnimationsChanged += enabled => AnimationsEnabled = enabled;
        _theming.CustomBackgroundStyleChanged += shader => CustomShaderFile = shader;
        _theming.BackgroundTransitionsChanged += enabled => TransitionsEnabled = enabled;

        BackgroundStyles = new AvaloniaList<AristeusBackgroundStyle>(Enum.GetValues<AristeusBackgroundStyle>());
        _theme = AristeusTheme.GetInstance();

        // Subscribe to the navigation service (when a page navigation is requested)
        pageNavigationService.NavigationRequested += pageType =>
        {
            var page = DemoPages.FirstOrDefault(x => x.GetType() == pageType);
            if (page is null || ActivePage?.GetType() == pageType) return;
            ActivePage = page;
        };

        Themes = _theme.ColorThemes;
        BaseTheme = _theme.ActiveBaseTheme;

        // Subscribe to the base theme changed events
        _theme.OnBaseThemeChanged += variant =>
        {
            BaseTheme = variant;
            ToastManager.CreateSimpleInfoToast()
                .WithTitle("Theme Changed")
                .WithContent($"Theme has changed to {variant}.")
                .Queue();
        };

        // Subscribe to the color theme changed events
        _theme.OnColorThemeChanged += theme => ToastManager.CreateSimpleInfoToast()
            .WithTitle("Color Changed")
            .WithContent($"Color has changed to {theme.DisplayName}.")
            .Queue();
    }

    [RelayCommand]
    private void ToggleAnimations()
    {
        AnimationsEnabled = !AnimationsEnabled;
        ToastManager.CreateSimpleInfoToast()
            .WithTitle(AnimationsEnabled ? "Animation Enabled" : "Animation Disabled")
            .WithContent(AnimationsEnabled ? "Background animations are now enabled." : "Background animations are now disabled.")
            .Queue();
    }

    [RelayCommand]
    private void ToggleTransitions()
    {
        TransitionsEnabled = !TransitionsEnabled;
        ToastManager.CreateSimpleInfoToast()
            .WithTitle(TransitionsEnabled ? "Transitions Enabled" : "Transitions Disabled")
            .WithContent(TransitionsEnabled ? "Background transitions are now enabled." : "Background transitions are now disabled.")
            .Queue();
    }

    [RelayCommand]
    private void ToggleBaseTheme() =>
        _theme.SwitchBaseTheme();

    public void ChangeTheme(AristeusColorTheme theme) =>
        _theme.ChangeColorTheme(theme);

    [RelayCommand]
    private void ShadCnMode()
    {
        Shadcn.Configure(Application.Current, Application.Current.ActualThemeVariant);
    }

    [RelayCommand]
    private void CreateCustomTheme()
    {
        DialogManager.CreateDialog()
            .WithViewModel(dialog => new CustomThemeDialogViewModel(_theme, dialog))
            .TryShow();
    }

    [RelayCommand]
    private void ToggleWindowLock()
    {
        WindowLocked = !WindowLocked;
        ToastManager.CreateSimpleInfoToast()
            .WithTitle($"Window {(WindowLocked ? "Locked" : "Unlocked")}")
            .WithContent($"Window has been {(WindowLocked ? "locked" : "unlocked")}.")
            .Queue();
    }

    [RelayCommand]
    private void ToggleTitleBackground()
    {
        ShowTitleBar = !ShowTitleBar;
        ShowBottomBar = !ShowBottomBar;
    }

    [RelayCommand]
    private void ToggleTitleBar()
    {
        TitleBarVisible = !TitleBarVisible;
        ToastManager.CreateSimpleInfoToast()
            .WithTitle($"Title Bar {(TitleBarVisible ? "Visible" : "Hidden")}")
            .WithContent($"Window title bar has been {(TitleBarVisible ? "shown" : "hidden")}.")
            .Queue();
    }

    [RelayCommand]
    private void ToggleRightToLeft() => _theme.IsRightToLeft = !_theme.IsRightToLeft;

    [RelayCommand]
    private static void OpenUrl(string url) => UrlUtilities.OpenUrl(url);

    partial void OnBackgroundStyleChanged(AristeusBackgroundStyle value) =>
        _theming.BackgroundStyle = value;

    partial void OnAnimationsEnabledChanged(bool value) =>
        _theming.BackgroundAnimations = value;

    partial void OnTransitionsEnabledChanged(bool value) =>
        _theming.BackgroundTransitions = value;
}