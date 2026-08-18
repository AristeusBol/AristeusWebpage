using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.Metadata;
using Avalonia.Controls.Primitives;
using AristeusUI.Enums;

namespace AristeusUI.Controls;

[TemplatePart("PART_Root", typeof(Panel))]
[TemplatePart("PART_VisualLayerManager", typeof(VisualLayerManager))]
[TemplatePart("PART_Background", typeof(AristeusBackground))]
public class AristeusMainHost : ContentControl
{
    // Background properties
    public static readonly StyledProperty<bool> BackgroundAnimationEnabledProperty =
        AvaloniaProperty.Register<AristeusMainHost, bool>(nameof(BackgroundAnimationEnabled), defaultValue: false);

    /// <inheritdoc cref="AristeusBackground.AnimationEnabled"/>
    public bool BackgroundAnimationEnabled
    {
        get => GetValue(BackgroundAnimationEnabledProperty);
        set => SetValue(BackgroundAnimationEnabledProperty, value);
    }

    public static readonly StyledProperty<AristeusBackgroundStyle> BackgroundStyleProperty =
        AvaloniaProperty.Register<AristeusMainHost, AristeusBackgroundStyle>(nameof(BackgroundStyle),
            defaultValue: AristeusBackgroundStyle.GradientSoft);

    /// <inheritdoc cref="AristeusBackground.Style"/>
    public AristeusBackgroundStyle BackgroundStyle
    {
        get => GetValue(BackgroundStyleProperty);
        set => SetValue(BackgroundStyleProperty, value);
    }

    public static readonly StyledProperty<string?> BackgroundShaderFileProperty =
        AvaloniaProperty.Register<AristeusMainHost, string?>(nameof(BackgroundShaderFile));

    /// <inheritdoc cref="AristeusBackground.ShaderFile"/>
    public string? BackgroundShaderFile
    {
        get => GetValue(BackgroundShaderFileProperty);
        set => SetValue(BackgroundShaderFileProperty, value);
    }

    public static readonly StyledProperty<string?> BackgroundShaderCodeProperty =
        AvaloniaProperty.Register<AristeusMainHost, string?>(nameof(BackgroundShaderCode));

    /// <inheritdoc cref="AristeusBackground.ShaderCode"/>
    public string? BackgroundShaderCode
    {
        get => GetValue(BackgroundShaderCodeProperty);
        set => SetValue(BackgroundShaderCodeProperty, value);
    }

    public static readonly StyledProperty<bool> BackgroundTransitionsEnabledProperty =
        AvaloniaProperty.Register<AristeusMainHost, bool>(nameof(BackgroundTransitionsEnabled), defaultValue: false);

    /// <inheritdoc cref="AristeusBackground.TransitionsEnabled"/>
    public bool BackgroundTransitionsEnabled
    {
        get => GetValue(BackgroundTransitionsEnabledProperty);
        set => SetValue(BackgroundTransitionsEnabledProperty, value);
    }

    public static readonly StyledProperty<double> BackgroundTransitionTimeProperty =
        AvaloniaProperty.Register<AristeusMainHost, double>(nameof(BackgroundTransitionTime), defaultValue: 1.0);

    /// <inheritdoc cref="AristeusBackground.TransitionTime"/>
    public double BackgroundTransitionTime
    {
        get => GetValue(BackgroundTransitionTimeProperty);
        set => SetValue(BackgroundTransitionTimeProperty, value);
    }

    public static readonly StyledProperty<bool> BackgroundForceSoftwareRenderingProperty =
        AvaloniaProperty.Register<AristeusMainHost, bool>(nameof(BackgroundForceSoftwareRendering));

    /// <summary>
    /// Forces the background of the window to utilise software rendering.
    /// This prevents use of any advanced effects or animations and provides only a flat background colour that changes with the theme.
    /// </summary>
    public bool BackgroundForceSoftwareRendering
    {
        get => GetValue(BackgroundForceSoftwareRenderingProperty);
        set => SetValue(BackgroundForceSoftwareRenderingProperty, value);
    }

    public static readonly StyledProperty<Avalonia.Controls.Controls> HostsProperty =
        AvaloniaProperty.Register<AristeusMainHost, Avalonia.Controls.Controls>(nameof(Hosts));

    /// <summary>
    /// These controls are displayed above all others and fill the entire window.
    /// You can include <see cref="AristeusDialogHost"/> and <see cref="AristeusToastHost"/> or create your own custom implementations.
    /// </summary>
    public Avalonia.Controls.Controls Hosts
    {
        get => GetValue(HostsProperty);
        set => SetValue(HostsProperty, value);
    }

    public AristeusMainHost()
    {
        Hosts = [];
    }
}