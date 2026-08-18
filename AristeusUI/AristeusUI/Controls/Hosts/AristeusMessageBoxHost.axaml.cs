using Avalonia;
using Avalonia.Collections;
using Avalonia.Controls;
using Avalonia.Controls.Metadata;
using Avalonia.Controls.Presenters;
using Avalonia.Controls.Primitives;
using AristeusUI.MessageBox;

namespace AristeusUI.Controls;

[TemplatePart("PART_Root", typeof(Border))]
[TemplatePart("PART_AlternativeHeaderGlassCard", typeof(GlassCard))]
[TemplatePart("PART_AlternativeHeaderGrid", typeof(Grid))]
[TemplatePart("PART_AlternativeIcon", typeof(ContentPresenter))]
[TemplatePart("PART_AlternativeHeader", typeof(ContentPresenter))]
[TemplatePart("PART_HeaderGrid", typeof(Grid))]
[TemplatePart("PART_Icon", typeof(ContentPresenter))]
[TemplatePart("PART_Header", typeof(ContentPresenter))]
[TemplatePart("PART_ContentGlassCard", typeof(GlassCard))]
[TemplatePart("PART_Content", typeof(ScrollViewer))]
[TemplatePart("PART_FooterGlassCard", typeof(GlassCard))]
[TemplatePart("PART_FooterGrid", typeof(Grid))]
[TemplatePart("PART_LeftContentItems", typeof(ItemsControl))]
[TemplatePart("PART_ActionButtons", typeof(ItemsControl))]
public class AristeusMessageBoxHost : HeaderedContentControl
{
    private const int DefaultItemsSpacing = 10;
    private const double DefaultIconPresetSize = 24;


    /// <summary>
    /// Defines the <see cref="UseAlternativeHeaderStyle"/> property.
    /// </summary>
    public static readonly StyledProperty<bool> UseAlternativeHeaderStyleProperty = AvaloniaProperty.Register<AristeusMessageBoxHost, bool>(nameof(UseAlternativeHeaderStyle));

    /// <summary>
    /// Gets or sets a value indicating whether to use the alternative header style.
    /// </summary>
    public bool UseAlternativeHeaderStyle
    {
        get => GetValue(UseAlternativeHeaderStyleProperty);
        set => SetValue(UseAlternativeHeaderStyleProperty, value);
    }

    public static readonly StyledProperty<object?> IconProperty = AvaloniaProperty.Register<AristeusMessageBoxHost, object?>(nameof(Icon));

    /// <summary>
    /// Gets or sets the icon content to display on the header.
    /// </summary>
    public object? Icon
    {
        get => GetValue(IconProperty);
        set => SetValue(IconProperty, value);
    }

    /// <summary>
    /// Defines the <see cref="IconPreset"/> property.
    /// </summary>
    public static readonly StyledProperty<AristeusMessageBoxIcons?> IconPresetProperty =
        AvaloniaProperty.Register<AristeusMessageBoxHost, AristeusMessageBoxIcons?>(nameof(IconPreset));

    /// <summary>
    /// Gets or sets the preset icon to display on the header.
    /// </summary>
    public AristeusMessageBoxIcons? IconPreset
    {
        get => GetValue(IconPresetProperty);
        set => SetValue(IconPresetProperty, value);
    }

    /// <summary>
    /// Defines the <see cref="IconPresetSize"/> property.
    /// </summary>
    public static readonly StyledProperty<double> IconPresetSizeProperty =
        AvaloniaProperty.Register<AristeusMessageBoxHost, double>(nameof(IconPresetSize), DefaultIconPresetSize);

    /// <summary>
    /// Gets or sets the size of the preset icon.
    /// </summary>
    public double IconPresetSize
    {
        get => GetValue(IconPresetSizeProperty);
        set => SetValue(IconPresetSizeProperty, value);
    }

    /// <summary>
    /// Defines the <see cref="ShowHeaderContentSeparator"/> property.
    /// </summary>
    public static readonly StyledProperty<bool> ShowHeaderContentSeparatorProperty =
        AvaloniaProperty.Register<AristeusMessageBoxHost, bool>(nameof(ShowHeaderContentSeparator));

    /// <summary>
    /// Gets or sets a value indicating whether to show the header/content separator.
    /// </summary>
    /// <remarks>Only visible if <see cref="UseAlternativeHeaderStyle"/> is <c>false</c>.</remarks>
    public bool ShowHeaderContentSeparator
    {
        get => GetValue(ShowHeaderContentSeparatorProperty);
        set => SetValue(ShowHeaderContentSeparatorProperty, value);
    }

    /// <summary>
    /// Defines the <see cref="FooterLeftItemsSource"/> property.
    /// </summary>
    public static readonly StyledProperty<Avalonia.Controls.Controls?> FooterLeftItemsSourceProperty =
        AvaloniaProperty.Register<AristeusMessageBoxHost, Avalonia.Controls.Controls?>(nameof(FooterLeftItemsSource));

    /// <summary>
    /// Gets or sets the items source to display in the footer left of the message box
    /// </summary>
    public Avalonia.Controls.Controls? FooterLeftItemsSource
    {
        get => GetValue(FooterLeftItemsSourceProperty);
        set => SetValue(FooterLeftItemsSourceProperty, value);
    }

    /// <summary>
    /// Defines the <see cref="ActionButtonsSource"/> property.
    /// </summary>
    public static readonly StyledProperty<AvaloniaList<Button>?> ActionButtonsSourceProperty =
        AvaloniaProperty.Register<AristeusMessageBoxHost, AvaloniaList<Button>?>(nameof(ActionButtonsSource));

    /// <summary>
    /// Gets or sets the action buttons to display in bottom right of the message box.
    /// </summary>
    public AvaloniaList<Button>? ActionButtonsSource
    {
        get => GetValue(ActionButtonsSourceProperty);
        set => SetValue(ActionButtonsSourceProperty, value);
    }

    /// <summary>
    /// Defines the <see cref="ActionButtonsPreset"/> property.
    /// </summary>
    public static readonly StyledProperty<AristeusMessageBoxButtons?> ActionButtonsPresetProperty =
        AvaloniaProperty.Register<AristeusMessageBoxHost, AristeusMessageBoxButtons?>(nameof(ActionButtonsPreset));

    /// <summary>
    /// Gets or sets the action buttons to display in bottom right of the message box.
    /// </summary>
    public AristeusMessageBoxButtons? ActionButtonsPreset
    {
        get => GetValue(ActionButtonsPresetProperty);
        set => SetValue(ActionButtonsPresetProperty, value);
    }

    /// <summary>
    /// Defines the <see cref="ItemsSpacing"/> property.
    /// </summary>
    public static readonly StyledProperty<int> ItemsSpacingProperty =
        AvaloniaProperty.Register<AristeusMessageBoxHost, int>(nameof(ItemsSpacing), DefaultItemsSpacing);

    /// <summary>
    /// Gets or sets the spacing between the items (<see cref="FooterLeftItemsSource"/> and <see cref="ActionButtonsSource"/>) in the message box.
    /// </summary>
    public int ItemsSpacing
    {
        get => GetValue(ItemsSpacingProperty);
        set => SetValue(ItemsSpacingProperty, value);
    }

    public AristeusMessageBoxHost()
    {
        FooterLeftItemsSource = [];
        ActionButtonsSource = [];
    }


    protected override void OnPropertyChanged(AvaloniaPropertyChangedEventArgs e)
    {
        base.OnPropertyChanged(e);

        if (ReferenceEquals(e.Property, IconPresetProperty) ||
            ReferenceEquals(e.Property, IconPresetSizeProperty))
        {
            var preset = IconPreset;
            if (preset is null) return;

            Icon = AristeusMessageBoxIconsFactory.CreateIcon(preset.Value, IconPresetSize);
        }
        else if (ReferenceEquals(e.Property, ActionButtonsPresetProperty))
        {
            var preset = ActionButtonsPreset;
            if (preset is null) return;

            Button[] buttons = preset switch
            {
                AristeusMessageBoxButtons.OK =>
                [
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.OK)
                ],
                AristeusMessageBoxButtons.OKAbort =>
                [
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.OK),
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.Abort)
                ],
                AristeusMessageBoxButtons.OKCancel =>
                [
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.OK),
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.Cancel)
                ],
                AristeusMessageBoxButtons.YesNo =>
                [
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.Yes),
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.No)
                ],
                AristeusMessageBoxButtons.YesNoAbort =>
                [
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.Yes),
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.No),
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.Abort)
                ],
                AristeusMessageBoxButtons.YesNoCancel =>
                [
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.Yes),
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.No),
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.Cancel)
                ],
                AristeusMessageBoxButtons.YesIgnore =>
                [
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.Yes),
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.Ignore)
                ],
                AristeusMessageBoxButtons.ApplyCancel =>
                [
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.Apply),
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.Cancel)
                ],
                AristeusMessageBoxButtons.RetryCancel =>
                [
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.Retry),
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.Cancel)
                ],
                AristeusMessageBoxButtons.RetryIgnoreAbort =>
                [
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.Retry),
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.Ignore),
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.Abort)
                ],
                AristeusMessageBoxButtons.RetryContinueCancel =>
                [
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.Retry),
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.Continue),
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.Cancel)
                ],
                AristeusMessageBoxButtons.Close =>
                [
                    AristeusMessageBoxButtonsFactory.CreateButton(AristeusMessageBoxResult.Close)
                ],
                _ => throw new ArgumentOutOfRangeException(nameof(preset), preset, null)
            };

            if (ActionButtonsSource is null)
            {
                ActionButtonsSource = new AvaloniaList<Button>(buttons);
            }
            else
            {
                ActionButtonsSource.Clear();
                ActionButtonsSource.AddRange(buttons);
            }
        }
    }

    public void ResetToDefaults()
    {
        UseAlternativeHeaderStyle = false;
        ShowHeaderContentSeparator = false;

        Icon = null;
        IconPreset = null;
        IconPresetSize = DefaultIconPresetSize;
        Content = null;

        FooterLeftItemsSource?.Clear();
        ActionButtonsSource?.Clear();
        ActionButtonsPreset = null;

        ItemsSpacing = DefaultItemsSpacing;
    }
}