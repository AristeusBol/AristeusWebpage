using Avalonia;
using Avalonia.Collections;
using Avalonia.Controls;
using Avalonia.Data;
using Avalonia.Markup.Xaml;
using Avalonia.Media;
using Avalonia.Styling;
using AristeusUI.Enums;
using AristeusUI.Extensions;
using AristeusUI.Locale;
using AristeusUI.Models;
using System.Globalization;

namespace AristeusUI;

public partial class AristeusTheme : Styles
{
    public static readonly StyledProperty<string?> LocaleProperty = AvaloniaProperty.Register<AristeusTheme, string?>(nameof(Locale));

    public static readonly StyledProperty<AristeusColor> ThemeColorProperty =
        AvaloniaProperty.Register<AristeusTheme, AristeusColor>(nameof(Color), defaultBindingMode: BindingMode.OneTime,
            defaultValue: AristeusColor.Blue);

    public static readonly StyledProperty<bool> IsRightToLeftProperty =
        AvaloniaProperty.Register<AristeusTheme, bool>(nameof(IsRightToLeft), defaultBindingMode: BindingMode.OneTime,
            defaultValue: false);

    /// <summary>
    /// Used to assign the ColorTheme at launch,
    /// </summary>
    public AristeusColor ThemeColor {
        get => GetValue(ThemeColorProperty);
        set {
            SetValue(ThemeColorProperty, value);
            SetColorThemeResourcesOnColorThemeChanged();
        }
    }

    public bool IsRightToLeft {
        get => GetValue(IsRightToLeftProperty);
        set => SetValue(IsRightToLeftProperty, value);
    }

    /// <summary>
    /// Called whenever the application's <see cref="AristeusColorTheme"/> is changed.
    /// Useful where controls cannot use "DynamicResource"
    /// </summary>
    public Action<AristeusColorTheme>? OnColorThemeChanged { get; set; }

    /// <summary>
    /// Called whenever the application's <see cref="ThemeVariant"/> is changed.
    /// Useful where controls need to change based on light/dark.
    /// </summary>
    public Action<ThemeVariant>? OnBaseThemeChanged { get; set; }

    /// <summary>
    /// Currently active <see cref="AristeusColorTheme"/>
    /// If you want to change this please use <see cref="ChangeColorTheme(AristeusUI.Models.AristeusColorTheme)"/>
    /// </summary>
    public AristeusColorTheme? ActiveColorTheme { get; private set; }

    /// <summary>
    /// All available Color Themes.
    /// </summary>
    public IAvaloniaReadOnlyList<AristeusColorTheme> ColorThemes => _allThemes;

    /// <summary>
    /// Currently active <see cref="ThemeVariant"/>
    /// If you want to change this please use <see cref="ChangeBaseTheme"/> or <see cref="SwitchBaseTheme"/>
    /// </summary>
    public ThemeVariant ActiveBaseTheme => _app.ActualThemeVariant;

    private readonly Application _app;

    private readonly HashSet<AristeusColorTheme> _colorThemeHashset = [];
    private readonly AvaloniaList<AristeusColorTheme> _allThemes = [];

    public AristeusTheme()
    {
        AvaloniaXamlLoader.Load(this);
        _app = Application.Current!;
        _app.ActualThemeVariantChanged += (_, e) => OnBaseThemeChanged?.Invoke(_app.ActualThemeVariant);
        foreach (var theme in DefaultColorThemes)
            AddColorTheme(theme.Value);

        UpdateFlowDirectionResources(IsRightToLeft);
    }

    protected override void OnPropertyChanged(AvaloniaPropertyChangedEventArgs change)
    {
        if (change.Property == IsRightToLeftProperty) {
            UpdateFlowDirectionResources(change.GetNewValue<bool>());
        }

        base.OnPropertyChanged(change);
    }

    /// <summary>
    /// Change the theme to one of the default themes.
    /// </summary>
    /// <param name="aristeusColor">The <see cref="AristeusColor"/> to change to.</param>
    public void ChangeColorTheme(AristeusColor aristeusColor) =>
        ThemeColor = aristeusColor;

    /// <summary>
    /// Tries to change the theme to a specific theme, this can be either a default or a custom defined one.
    /// </summary>
    /// <param name="aristeusColorTheme"></param>
    public void ChangeColorTheme(AristeusColorTheme aristeusColorTheme) =>
        SetColorTheme(aristeusColorTheme);

    /// <summary>
    /// Blindly switches to the "next" theme available in the <see cref="ColorThemes"/> collection.
    /// </summary>
    public void SwitchColorTheme()
    {
        var index = -1;
        for (var i = 0; i < ColorThemes.Count; i++) {
            if (ColorThemes[i] != ActiveColorTheme) continue;
            index = i;
            break;
        }
        if (index == -1) return;
        var newIndex = (index + 1) % ColorThemes.Count;
        var newColorTheme = ColorThemes[newIndex];
        ChangeColorTheme(newColorTheme);
    }

    /// <summary>
    /// Add a new <see cref="AristeusColorTheme"/> to the ones available, without making it active.
    /// </summary>
    /// <param name="aristeusColorTheme">New <see cref="AristeusColorTheme"/> to add.</param>
    public void AddColorTheme(AristeusColorTheme aristeusColorTheme)
    {
        if (_colorThemeHashset.Contains(aristeusColorTheme))
            throw new InvalidOperationException("This color theme has already been added.");
        _colorThemeHashset.Add(aristeusColorTheme);
        _allThemes.Add(aristeusColorTheme);
    }

    /// <summary>
    /// Adds multiple new <see cref="AristeusColorTheme"/> to the ones available, without making any active.
    /// </summary>
    /// <param name="aristeusColorThemes">A collection of new <see cref="AristeusColorTheme"/> to add.</param>
    public void AddColorThemes(IEnumerable<AristeusColorTheme> aristeusColorThemes)
    {
        foreach (var colorTheme in aristeusColorThemes)
            AddColorTheme(colorTheme);
    }

    /// <summary>
    /// Tries to change the base theme to the one provided, if it is different.
    /// </summary>
    /// <param name="baseTheme"><see cref="ThemeVariant"/> to change to.</param>
    public void ChangeBaseTheme(ThemeVariant baseTheme)
    {
        if (_app.ActualThemeVariant == baseTheme) return;
        _app.RequestedThemeVariant = baseTheme;

        SetColorThemeResourcesOnColorThemeChanged();
    }

    /// <summary>
    /// Simply switches from Light -> Dark and visa versa.
    /// </summary>
    public void SwitchBaseTheme()
    {
        if (Application.Current is null) return;
        var newBase = Application.Current.ActualThemeVariant == ThemeVariant.Dark
            ? ThemeVariant.Light
            : ThemeVariant.Dark;
        Application.Current.RequestedThemeVariant = newBase;

        SetColorThemeResourcesOnColorThemeChanged();
    }

    private void UpdateFlowDirectionResources(bool rightToLeft)
    {
        var primary = rightToLeft ? FlowDirection.RightToLeft : FlowDirection.LeftToRight;
        var opposite = rightToLeft ? FlowDirection.LeftToRight : FlowDirection.RightToLeft;

        Resources["FlowDirectionPrimary"] = primary;
        Resources["FlowDirectionOpposite"] = opposite;
    }

    /// <summary>
    /// Initializes the color theme resources whenever the property is changed.
    /// In an ideal world people wouldn't use the property
    /// </summary>
    private void SetColorThemeResourcesOnColorThemeChanged()
    {
        if (!DefaultColorThemes.TryGetValue(ThemeColor, out var colorTheme))
            throw new Exception($"{ThemeColor} has no defined color theme.");
        SetColorTheme(colorTheme);
    }

    private void SetColorTheme(AristeusColorTheme colorTheme)
    {
        SetColorWithOpacities("AristeusPrimaryColor", colorTheme.Primary);
        SetResource("AristeusPrimaryDarkColor", colorTheme.PrimaryDark);
        SetColorWithOpacities("AristeusAccentColor", colorTheme.Accent);
        SetResource("AristeusAccentDarkColor", colorTheme.AccentDark);
        ActiveColorTheme = colorTheme;
        OnColorThemeChanged?.Invoke(ActiveColorTheme);
    }

    private void SetColorWithOpacities(string baseName, Color baseColor)
    {
        SetResource(baseName, baseColor);
        SetResource($"{baseName}75", baseColor.WithAlpha(0.75));
        SetResource($"{baseName}50", baseColor.WithAlpha(0.50));
        SetResource($"{baseName}25", baseColor.WithAlpha(0.25));
        SetResource($"{baseName}20", baseColor.WithAlpha(0.2));
        SetResource($"{baseName}15", baseColor.WithAlpha(0.15));
        SetResource($"{baseName}10", baseColor.WithAlpha(0.10));
        SetResource($"{baseName}7", baseColor.WithAlpha(0.07));
        SetResource($"{baseName}5", baseColor.WithAlpha(0.05));
        SetResource($"{baseName}3", baseColor.WithAlpha(0.03));
        SetResource($"{baseName}1", baseColor.WithAlpha(0.005));
        SetResource($"{baseName}0", baseColor.WithAlpha(0.00));

        if (ActiveBaseTheme == ThemeVariant.Dark) {
            SetResource($"{baseName}120", Lighten(baseColor, 0.7));
            SetResource($"{baseName}150", Lighten(baseColor, 1));
        }
        else {
            SetResource($"{baseName}120", baseColor);
            SetResource($"{baseName}150", baseColor);
        }
    }

    public static Color Lighten(Color color, double amount)
    {
        amount = Clamp(amount, 0.0, 1.0);

        byte lighten(byte component)
        {
            int result = (int)(component + (255 - component) * amount);
            return (byte)Clamp(result, 0, 255);
        }

        return Color.FromArgb(
            color.A,
            lighten(color.R),
            lighten(color.G),
            lighten(color.B)
        );
    }

    public static double Clamp(double value, double min, double max)
    {
        return value < min ? min : (value > max ? max : value);
    }

    private static int Clamp(int value, int min, int max)
    {
        return value < min ? min : (value > max ? max : value);
    }

    private void SetResource(string name, Color color) =>
        _app.Resources[name] = color;

    // Static Members...

    /// <summary>
    /// The default Color Themes included with AristeusUI.
    /// </summary>
    public static readonly IReadOnlyDictionary<AristeusColor, AristeusColorTheme> DefaultColorThemes;

    static AristeusTheme()
    {
        var defaultThemes = new[]
        {
            new DefaultAristeusColorTheme(AristeusColor.Orange, Color.Parse("#d48806"), Color.Parse("#176CE8")),
            new DefaultAristeusColorTheme(AristeusColor.Red, Color.Parse("#D03A2F"), Color.Parse("#2FC5D0")),
            new DefaultAristeusColorTheme(AristeusColor.Green, Color.Parse("#537834"), Color.Parse("#B24DB0")),
            new DefaultAristeusColorTheme(AristeusColor.Blue, Color.Parse("#0A59F7"), Color.Parse("#F7A80A")),
        };
        DefaultColorThemes = defaultThemes.ToDictionary(x => x.ThemeColor, y => (AristeusColorTheme)y);
    }

    /// <summary>
    /// Retrieves an instance tied to a specific instance of an application.
    /// </summary>
    /// <returns>A <see cref="AristeusTheme"/> instance that can be used to change themes.</returns>
    /// <exception cref="InvalidOperationException">Thrown if no AristeusTheme has been defined in App.axaml.</exception>
    public static AristeusTheme GetInstance(Application app)
    {
        var theme = app.Styles.FirstOrDefault(style => style is AristeusTheme);
        if (theme is not AristeusTheme aristeusTheme)
            throw new InvalidOperationException(
                "No AristeusTheme instance available. Ensure AristeusTheme has been set in Application.Styles in App.axaml.");
        return aristeusTheme;
    }

    /// <summary>
    /// Retrieves an instance tied to the currently active application.
    /// </summary>
    /// <returns>A <see cref="AristeusTheme"/> instance that can be used to change themes.</returns>
    /// <exception cref="InvalidOperationException">Thrown if no AristeusTheme has been defined in App.axaml.</exception>
    public static AristeusTheme GetInstance() => GetInstance(Application.Current!);

    // Localization

    private static readonly Dictionary<string, ResourceDictionary> LocaleToResource = new()
    {
        { "en-US", new en_US() },
        { "nl-NL", new nl_NL() },
        { "pt-PT", new pt_PT() },
        { "zh-CN", new zh_CN() },
        { "de-DE", new de_DE() },
        { "es-ES", new es_ES() },
        { "fr-FR", new fr_FR() },
        { "it-IT", new it_IT() },
        { "ru-RU", new ru_RU() },
        { "ja-JP", new ja_JP() }
    };

    private static readonly ResourceDictionary DefaultResource = new en_US();

    private string? _locale;
    public string? Locale {
        get => _locale;
        set {
            try {
                if (TryGetLocaleResource(value, out var resource) && resource is not null) {
                    _locale = value;
                    foreach (var keyValue in resource) Resources[keyValue.Key] = keyValue.Value;
                }
                else {
                    _locale = CultureInfo.CurrentCulture.Name;
                    foreach (var keyValue in DefaultResource) Resources[keyValue.Key] = keyValue.Value;
                }
            }
            catch {
                _locale = CultureInfo.InvariantCulture.Name;
            }
        }
    }

    private static bool TryGetLocaleResource(string? locale, out ResourceDictionary? resourceDictionary)
    {
        if (LocaleToResource.TryGetValue(locale ?? string.Empty, out var resource)) {
            resourceDictionary = resource;
            return true;
        }

        resourceDictionary = DefaultResource;
        return false;
    }

    public static void OverrideLocaleResources(Application application, CultureInfo? culture)
    {
        if (culture is null) return;
        if (!LocaleToResource.TryGetValue(culture.Name, out var resources)) return;
        foreach (var keyValue in resources) {
            application.Resources[keyValue.Key] = keyValue.Value;
        }
    }

    public static void OverrideLocaleResources(StyledElement element, CultureInfo? culture)
    {
        if (culture is null) return;
        if (!LocaleToResource.TryGetValue(culture.Name, out var resources)) return;
        foreach (var keyValue in resources) {
            element.Resources[keyValue.Key] = keyValue.Value;
        }
    }
}