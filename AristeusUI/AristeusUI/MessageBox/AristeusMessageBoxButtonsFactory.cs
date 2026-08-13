using Avalonia;
using Avalonia.Controls;
using Avalonia.Layout;
using Avalonia.Media;
using AristeusUI.Content;

namespace AristeusUI.MessageBox;

/// <summary>
/// Factory for creating buttons for the message box.
/// </summary>
public static class AristeusMessageBoxButtonsFactory
{
    /// <summary>
    /// Creates a new Button configured for use as a message box action.
    /// </summary>
    /// <remarks>The returned button always includes the 'MessageBoxAction' class in addition to any classes
    /// provided. The link parameter is stored in the button's tag and does not affect the button's visual appearance
    /// directly.</remarks>
    /// <param name="content">The content to display within the button. This can be any object, such as a string or a UI element. If null, the
    /// button will have no content.</param>
    /// <param name="classes">A space-separated list of CSS class names to apply to the button. If null or empty, only the default
    /// 'MessageBoxAction' class is applied.</param>
    /// <param name="link">An optional link associated with the button. If specified, the link is stored in the button's tag for later use.</param>
    /// <returns>A Button instance configured with the specified content, classes, and link information.</returns>
    public static Button CreateButton(object? content = null, string? classes = null, string? link = null)
    {
        var button = new Button
        {
            Content = content,
            Tag = new AristeusMessageBoxButtonTag
            {
                Link = link
            }
        };

        if (!string.IsNullOrWhiteSpace(classes))
        {
            ///var split = classes!.Split([' '], StringSplitOptions.RemoveEmptyEntries);
            var split = classes!.Split(new char[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
            button.Classes.AddRange(split);
        }
        button.Classes.Add("MessageBoxAction");
        return button;
    }

    /// <summary>
    /// Creates a new button configured for a message box with the specified content, result value, optional
    /// classes, and optional link.
    /// </summary>
    /// <remarks>The returned button's <c>Tag</c> property is set to a <see cref="AristeusMessageBoxButtonTag"/>
    /// containing the specified result and link. This method is typically used to create buttons for custom message
    /// boxes where each button represents a distinct user choice.</remarks>
    /// <param name="content">The content to display within the button. This can be a string, UI element, or any object representing the
    /// button's label or visual content. Can be null for an empty button.</param>
    /// <param name="result">The result value associated with the button, indicating the action or response when the button is clicked.</param>
    /// <param name="classes">Optional CSS class names to apply to the button for custom styling. Can be null or empty if no additional
    /// styling is required.</param>
    /// <param name="link">An optional link to associate with the button. If specified, clicking the button will navigate to this
    /// link. Can be null if no link is needed.</param>
    /// <returns>A <see cref="Button"/> instance configured with the specified content, result value, CSS classes, and hyperlink.</returns>
    public static Button CreateButton(object? content, AristeusMessageBoxResult result, string? classes = null, string? link = null)
    {
        var button = CreateButton(content, classes);
        button.Tag = new AristeusMessageBoxButtonTag(result)
        {
            Link = link
        };
        return button;
    }


    /// <summary>
    /// Create and builds a button for the specified result.
    /// </summary>
    /// <param name="result"></param>
    /// <returns></returns>
    public static Button CreateButton(AristeusMessageBoxResult result)
    {
        var button = CreateButton(null, result, "Flat");

        var pathIcon = new PathIcon
        {
            Width = 12,
            Height = 12,
            Foreground = Brushes.White,
            Margin = new Thickness(0,0,5,0)
        };

        switch (result)
        {
            case AristeusMessageBoxResult.OK:
                button.IsDefault = true;
                pathIcon.Data = Icons.Check;
                break;
            case AristeusMessageBoxResult.Yes:
                button.IsDefault = true;
                pathIcon.Data = Icons.Check;
                break;
            case AristeusMessageBoxResult.No:
                button.IsCancel = true;
                pathIcon.Data = Icons.Cross;
                break;
            case AristeusMessageBoxResult.Cancel:
                button.IsCancel = true;
                pathIcon.Data = Icons.Cancel;
                break;
            case AristeusMessageBoxResult.Apply:
                button.IsDefault = true;
                pathIcon.Data = Icons.Check;
                break;
            case AristeusMessageBoxResult.Ignore:
                pathIcon.Data = Icons.DebugStepOver;
                break;
            case AristeusMessageBoxResult.Retry:
                button.IsDefault = true;
                pathIcon.Data = Icons.Refresh;
                break;
            case AristeusMessageBoxResult.Abort:
                button.IsCancel = true;
                pathIcon.Data = Icons.Cancel;
                break;
            case AristeusMessageBoxResult.Continue:
                pathIcon.Data = Icons.ArrowRight;
                break;
            case AristeusMessageBoxResult.Close:
                button.IsCancel = true;
                pathIcon.Data = Icons.Logout;
                break;
            default:
                throw new ArgumentOutOfRangeException(nameof(result), result, null);
        }

        Application.Current!.TryFindResource($"STRING_PROMPT_{result.ToString().ToUpperInvariant()}", out var buttonLocale);
        if (buttonLocale is not string buttonLocaleText)
        {
            buttonLocaleText = result.ToString();
        }

        button.Content = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 5,
            VerticalAlignment = VerticalAlignment.Center,
            Children =
            {
                pathIcon,
                new TextBlock
                {
                    VerticalAlignment = VerticalAlignment.Center,
                    Text = buttonLocaleText,
                }
            }
        };


        return button;
    }
}