using Avalonia;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Interactivity;
using Avalonia.Media;
using AristeusUI.Controls;
using AristeusUI.Extensions;

namespace AristeusUI.MessageBox;

/// <summary>
/// Message box factory.
/// </summary>
public static class AristeusMessageBox
{
    #region Create MessageBox
    /// <summary>
    /// Creates a base message box window.
    /// </summary>
    /// <param name="options"></param>
    /// <returns></returns>
    public static Window CreateMessageBoxWindow(AristeusMessageBoxOptions? options = null)
    {
        options ??= new AristeusMessageBoxOptions();

        Window window;

        if (options.UseNativeWindow)
        {
            window = new Window
            {
                WindowDecorations = options.IsTitleBarVisible ? WindowDecorations.Full : WindowDecorations.BorderOnly,
            };
            window.ConstrainMaxSizeToScreenRatio(options.MaxWidthScreenRatio, options.MaxHeightScreenRatio);
        }
        else
        {
            var aristeusWindow = new AristeusWindow
            {
                CanMinimize = options.CanMinimize,
                CanMaximize = options.CanMaximize,
                CanFullScreen = false,
                IsTitleBarVisible = options.IsTitleBarVisible,
                MaxWidthScreenRatio = options.MaxWidthScreenRatio,
                MaxHeightScreenRatio = options.MaxHeightScreenRatio,
            };

            if (options.BackgroundAnimationEnabled is not null) aristeusWindow.BackgroundAnimationEnabled = options.BackgroundAnimationEnabled.Value;
            if (options.BackgroundForceSoftwareRendering is not null) aristeusWindow.BackgroundForceSoftwareRendering = options.BackgroundForceSoftwareRendering.Value;
            if (options.BackgroundShaderFile is not null) aristeusWindow.BackgroundShaderFile = options.BackgroundShaderFile;
            if (options.BackgroundShaderCode is not null) aristeusWindow.BackgroundShaderCode = options.BackgroundShaderCode;
            if (options.BackgroundStyle is not null) aristeusWindow.BackgroundStyle = options.BackgroundStyle.Value;
            if (options.BackgroundTransitionTime is not null) aristeusWindow.BackgroundTransitionTime = options.BackgroundTransitionTime.Value;
            if (options.BackgroundTransitionsEnabled is not null) aristeusWindow.BackgroundTransitionsEnabled = options.BackgroundTransitionsEnabled.Value;
            if (options.LogoContent is not null) aristeusWindow.LogoContent = options.LogoContent;

            window = aristeusWindow;
        }

        // Shared properties
        if (options.Icon is not null) window.Icon = options.Icon;
        window.Topmost = options.Topmost;
        window.CanResize = options.CanResize;
        window.Title = options.Title;
        window.ShowInTaskbar = options.ShowInTaskbar;
        window.WindowStartupLocation = options.WindowStartupLocation;
        window.SizeToContent = options.SizeToContent;
        window.Width = options.Width;
        window.Height = options.Height;
        window.MinWidth = options.MinWidth;
        window.MinHeight = options.MinHeight;

        return window;
    }
    #endregion

    #region ShowDialog

    /// <summary>
    /// Displays a modal message box dialog with the specified content and options, and returns the result
    /// asynchronously.
    /// </summary>
    /// <remarks>If the owner window is a AristeusWindow, any unspecified options in windowOptions are inherited
    /// from the owner. The dialog is shown modally and blocks interaction with the owner window until closed. The
    /// returned result depends on the configuration of the message box's action buttons.</remarks>
    /// <param name="owner">The window that will act as the owner of the message box dialog. The dialog is centered relative to this window.
    /// Cannot be null.</param>
    /// <param name="messageBox">The message box host containing the content, header, and action buttons to display in the dialog. Cannot be
    /// null.</param>
    /// <param name="title">The title to display in the dialog window. If null, the title is determined by the window options or defaults to
    /// the owner's title.</param>
    /// <param name="windowOptions">The options used to configure the appearance and behavior of the message box window. If null, default options
    /// are used.</param>
    /// <returns>A task that represents the asynchronous operation. The task result contains the value associated with the button
    /// the user clicked, or null if the dialog was closed without a selection.</returns>
    public static async Task<object?> ShowDialog(Window owner, AristeusMessageBoxHost messageBox, string? title, AristeusMessageBoxOptions? windowOptions = null)
    {
        windowOptions ??= new AristeusMessageBoxOptions();

        if (owner is AristeusWindow aristeusWindow)
        {
            if (windowOptions.BackgroundAnimationEnabled is null) windowOptions = windowOptions with { BackgroundAnimationEnabled = aristeusWindow.BackgroundAnimationEnabled };
            if (windowOptions.BackgroundForceSoftwareRendering is null) windowOptions = windowOptions with { BackgroundForceSoftwareRendering = aristeusWindow.BackgroundForceSoftwareRendering };
            if (windowOptions.BackgroundShaderCode is null) windowOptions = windowOptions with { BackgroundShaderCode = aristeusWindow.BackgroundShaderCode };
            if (windowOptions.BackgroundShaderFile is null) windowOptions = windowOptions with { BackgroundShaderFile = aristeusWindow.BackgroundShaderFile };
            if (windowOptions.BackgroundStyle is null) windowOptions = windowOptions with { BackgroundStyle = aristeusWindow.BackgroundStyle };
            if (windowOptions.BackgroundTransitionTime is null) windowOptions = windowOptions with { BackgroundTransitionTime = aristeusWindow.BackgroundTransitionTime };
            if (windowOptions.BackgroundTransitionsEnabled is null) windowOptions = windowOptions with { BackgroundTransitionsEnabled = aristeusWindow.BackgroundTransitionsEnabled };
        }

        if (title is not null) windowOptions = windowOptions with { Title = title };

        var window = CreateMessageBoxWindow(windowOptions);
        window.Icon ??= owner.Icon;
        if (string.IsNullOrWhiteSpace(window.Title)) window.Title = $"{owner.Title} Message";
        window.Tag = messageBox;
        window.Closed += WindowOnClosed;

        if (messageBox.Header is string headerText)
        {
            messageBox.Header = new SelectableTextBlock
            {
                Text = headerText,
                Classes = { "h5" },
                TextWrapping = TextWrapping.Wrap
            };
        }

        if (messageBox.Content is string contentText)
        {
            messageBox.Content = new SelectableTextBlock
            {
                Text = contentText,
                TextWrapping = TextWrapping.Wrap
            };
        }

        var actionButtons = messageBox.ActionButtonsSource;
        // Subscribe events
        if (actionButtons is not null)
        {
            foreach (var button in actionButtons)
            {
                var tag = (button.Tag as AristeusMessageBoxButtonTag) ?? new AristeusMessageBoxButtonTag()
                {
                    Tag = button.Tag
                };
                tag.Owner = window;
                button.Tag = tag;
                button.Click += ActionButtonOnClick;
            }

            if (actionButtons.Count <= 1)
            {
                window.KeyUp += WindowOnKeyUp;
            }

            if (actionButtons.Count == 1)
            {
                actionButtons[0].IsCancel = true;
            }
        }
        else
        {
            window.KeyUp += WindowOnKeyUp;
        }

        if (windowOptions.UseNativeWindow)
        {
            var aristeusHost = new AristeusMainHost
            {
                Content = messageBox,
            };

            if (windowOptions.BackgroundAnimationEnabled is not null) aristeusHost.BackgroundAnimationEnabled = windowOptions.BackgroundAnimationEnabled.Value;
            if (windowOptions.BackgroundForceSoftwareRendering is not null) aristeusHost.BackgroundForceSoftwareRendering = windowOptions.BackgroundForceSoftwareRendering.Value;
            if (windowOptions.BackgroundShaderFile is not null) aristeusHost.BackgroundShaderFile = windowOptions.BackgroundShaderFile;
            if (windowOptions.BackgroundShaderCode is not null) aristeusHost.BackgroundShaderCode = windowOptions.BackgroundShaderCode;
            if (windowOptions.BackgroundStyle is not null) aristeusHost.BackgroundStyle = windowOptions.BackgroundStyle.Value;
            if (windowOptions.BackgroundTransitionTime is not null) aristeusHost.BackgroundTransitionTime = windowOptions.BackgroundTransitionTime.Value;
            if (windowOptions.BackgroundTransitionsEnabled is not null) aristeusHost.BackgroundTransitionsEnabled = windowOptions.BackgroundTransitionsEnabled.Value;

            window.Content = aristeusHost;
        }
        else
        {
            window.Content = messageBox;
        }

        var result = await window.ShowDialog<object?>(owner);

        // Unsubscribe events
        if (actionButtons is not null)
        {
            foreach (var button in actionButtons)
            {
                button.Click -= ActionButtonOnClick;
            }

            if (actionButtons.Count <= 1)
            {
                window.KeyUp -= WindowOnKeyUp;
            }
        }
        else
        {
            window.KeyUp -= WindowOnKeyUp;
        }

        // Dispose window if needed
        if (window is IDisposable disposable) disposable.Dispose();

        return result;
    }

    /// <summary>
    /// Displays a modal dialog box with the specified message box content and options, blocking interaction with the
    /// owner window until the dialog is closed.
    /// </summary>
    /// <param name="owner">The window that will own the modal dialog. The dialog will be centered relative to this window and block input
    /// to it while open.</param>
    /// <param name="messageBox">The message box content to display within the dialog. Specifies the message, buttons, and other UI elements.</param>
    /// <param name="windowOptions">Optional settings that configure the appearance and behavior of the dialog window. If null, default options are
    /// used.</param>
    /// <returns>A task that represents the asynchronous operation. The task result contains an object representing the user's
    /// response or selection, or null if the dialog was closed without a response.</returns>
    public static Task<object?> ShowDialog(Window owner, AristeusMessageBoxHost messageBox, AristeusMessageBoxOptions? windowOptions = null)
    {
        return ShowDialog(owner, messageBox, null, windowOptions);
    }

    /// <summary>
    /// Displays a modal dialog box using the specified message box host and returns the result asynchronously.
    /// </summary>
    /// <param name="messageBox">The message box host to display in the dialog. Cannot be null.</param>
    /// <param name="title">The title to display in the dialog window. If null, a default title is used.</param>
    /// <param name="windowOptions">Optional window options that configure the appearance and behavior of the dialog. If null, default options are
    /// applied.</param>
    /// <returns>A task that represents the asynchronous operation. The task result contains the value returned by the dialog, or
    /// null if the dialog was closed without a result.</returns>
    /// <exception cref="InvalidOperationException">Thrown if the application does not have a main window or is not running with a classic desktop style application
    /// lifetime.</exception>
    public static Task<object?> ShowDialog(AristeusMessageBoxHost messageBox, string? title, AristeusMessageBoxOptions? windowOptions = null)
    {
        if (Application.Current?.ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            if (desktop.MainWindow is not null)
            {
                return ShowDialog(desktop.MainWindow, messageBox, title, windowOptions);
            }

            throw new InvalidOperationException("The application does not contain a main window.");
        }

        throw new InvalidOperationException("The application is not an instance of IClassicDesktopStyleApplicationLifetime.");
    }

    /// <summary>
    /// Displays the specified message box as a modal dialog using the application's main window.
    /// </summary>
    /// <param name="messageBox">The message box to display in the dialog. Cannot be null.</param>
    /// <param name="windowOptions">Optional settings that configure the appearance and behavior of the dialog window. May be null to use default
    /// options.</param>
    /// <returns>A task that represents the asynchronous operation. The task result contains the value returned by the dialog, or
    /// null if the dialog was closed without a result.</returns>
    /// <exception cref="InvalidOperationException">Thrown if the application does not have a main window, or if the application lifetime is not an instance of
    /// IClassicDesktopStyleApplicationLifetime.</exception>
    public static Task<object?> ShowDialog(AristeusMessageBoxHost messageBox, AristeusMessageBoxOptions? windowOptions = null)
    {
        return ShowDialog(messageBox, null, windowOptions);
    }


    /// <summary>
    /// Displays a modal message box dialog and returns the result as a strongly typed value.
    /// </summary>
    /// <remarks>This method is only compatible with message boxes that use AristeusMessageBoxResult buttons. If a
    /// custom button type is used, an exception is thrown.</remarks>
    /// <param name="owner">The window that will own the message box dialog. This parameter cannot be null.</param>
    /// <param name="messageBox">The message box host that defines the content and buttons to display. This parameter cannot be null.</param>
    /// <param name="title">The title to display in the message box window. If null, a default title is used.</param>
    /// <param name="windowOptions">Optional settings that configure the appearance and behavior of the message box window. If null, default options
    /// are applied.</param>
    /// <returns>A task that represents the asynchronous operation. The task result is a AristeusMessageBoxResult value indicating
    /// which button was pressed, or Close if the dialog was closed without a button click.</returns>
    /// <exception cref="InvalidOperationException">Thrown if the dialog contains a button that does not correspond to a AristeusMessageBoxResult value.</exception>
    public static async Task<AristeusMessageBoxResult> ShowDialogResult(Window owner, AristeusMessageBoxHost messageBox, string? title, AristeusMessageBoxOptions? windowOptions = null)
    {
        var result = await ShowDialog(owner, messageBox, title, windowOptions);
        if (result is null) return AristeusMessageBoxResult.Close; // Closed without clicking a button
        if (result is AristeusMessageBoxResult mbResult) return mbResult;
        throw new InvalidOperationException("Unknown button type or custom button was used. This method is only compatible with AristeusMessageBoxResult buttons.");
    }

    /// <summary>
    /// Displays a message box dialog and asynchronously returns the user's response.
    /// </summary>
    /// <param name="owner">The window that will own the message box dialog. Can be null if no owner is required.</param>
    /// <param name="messageBox">The message box host that defines the content and behavior of the dialog to display.</param>
    /// <param name="windowOptions">Optional settings that configure the appearance and behavior of the message box window. Can be null to use
    /// default options.</param>
    /// <returns>A task that represents the asynchronous operation. The task result contains a value indicating the user's
    /// response to the message box.</returns>
    public static Task<AristeusMessageBoxResult> ShowDialogResult(Window owner, AristeusMessageBoxHost messageBox, AristeusMessageBoxOptions? windowOptions = null)
    {
        return ShowDialogResult(messageBox, null, windowOptions);
    }

    /// <summary>
    /// Displays a modal message box dialog with the specified content and returns the result indicating which button
    /// was pressed.
    /// </summary>
    /// <remarks>If the user closes the dialog without selecting a button, the result is
    /// AristeusMessageBoxResult.Close. This method only supports standard AristeusMessageBoxResult buttons; using custom
    /// buttons will result in an exception.</remarks>
    /// <param name="owner">The window that will own the message box dialog. Cannot be null.</param>
    /// <param name="message">The message text to display in the dialog.</param>
    /// <param name="buttons">The set of buttons to display in the message box. Determines which user actions are available.</param>
    /// <param name="title">The title text to display in the dialog's title bar. If null, a default title is used.</param>
    /// <param name="header">The header text to display above the message content. If null, no header is shown.</param>
    /// <param name="icon">The icon to display in the dialog. If null, no icon is shown.</param>
    /// <param name="windowOptions">Additional options for configuring the appearance and behavior of the message box window. If null, default
    /// options are used.</param>
    /// <returns>A task that represents the asynchronous operation. The task result is a AristeusMessageBoxResult value indicating
    /// which button was pressed, or Close if the dialog was closed without a button press.</returns>
    /// <exception cref="InvalidOperationException">Thrown if the dialog is configured with custom buttons or an unknown button type that is not compatible with
    /// AristeusMessageBoxResult.</exception>
    public static async Task<AristeusMessageBoxResult> ShowDialogResult(Window owner, string message, AristeusMessageBoxButtons buttons, string? title = null,
        string? header = null, AristeusMessageBoxIcons? icon = null, AristeusMessageBoxOptions? windowOptions = null)
    {
        var result = await ShowDialog(owner, new AristeusMessageBoxHost
        {
            Header = header,
            IconPreset = icon,
            Content = message,
            ActionButtonsPreset = buttons
        }, title, windowOptions);
        if (result is null) return AristeusMessageBoxResult.Close; // Closed without clicking a button
        if (result is AristeusMessageBoxResult mbResult) return mbResult;
        throw new InvalidOperationException("Unknown button type or custom button was used. This method is only compatible with AristeusMessageBoxResult buttons.");
    }

    /// <summary>
    /// Displays a message box dialog and asynchronously returns the user's response.
    /// </summary>
    /// <param name="messageBox">The message box to display in the dialog. Cannot be null.</param>
    /// <param name="title">The title to display in the dialog window. If null, a default title is used.</param>
    /// <param name="windowOptions">Optional window options that configure the appearance and behavior of the dialog. If null, default options are
    /// applied.</param>
    /// <returns>A task that represents the asynchronous operation. The task result contains a value indicating the user's selection
    /// in the message box.</returns>
    /// <exception cref="InvalidOperationException">Thrown if the application is not running with a classic desktop style lifetime, or if there is no main window
    /// available.</exception>
    public static Task<AristeusMessageBoxResult> ShowDialogResult(AristeusMessageBoxHost messageBox, string? title, AristeusMessageBoxOptions? windowOptions = null)
    {
        if (Application.Current?.ApplicationLifetime is not IClassicDesktopStyleApplicationLifetime desktop)
        {
            throw new InvalidOperationException("The application is not an instance of IClassicDesktopStyleApplicationLifetime.");
        }

        if (desktop.MainWindow is not null)
        {
            return ShowDialogResult(desktop.MainWindow, messageBox, title, windowOptions);
        }

        throw new InvalidOperationException("The application does not contain a main window.");
    }

    /// <summary>
    /// Displays a message box dialog and asynchronously returns the user's response.
    /// </summary>
    /// <param name="messageBox">The message box to display in the dialog. Cannot be null.</param>
    /// <param name="windowOptions">Optional window options that configure the appearance and behavior of the dialog. If null, default options are
    /// applied.</param>
    /// <returns>A task that represents the asynchronous operation. The task result contains a value indicating the user's selection
    /// in the message box.</returns>
    /// <exception cref="InvalidOperationException">Thrown if the application is not running with a classic desktop style lifetime, or if there is no main window
    /// available.</exception>
    public static Task<AristeusMessageBoxResult> ShowDialogResult(AristeusMessageBoxHost messageBox, AristeusMessageBoxOptions? windowOptions = null)
    {
        return ShowDialogResult(messageBox, null, windowOptions);
    }

    /// <summary>
    /// Displays a message box with the specified message, buttons, and options, and returns the user's response as an
    /// asynchronous operation.
    /// </summary>
    /// <remarks>This method displays the message box using the application's main window as the owner. Use
    /// this overload when you want to show a message box without explicitly specifying a parent window.</remarks>
    /// <param name="message">The text to display in the body of the message box. Cannot be null.</param>
    /// <param name="buttons">A value that specifies which buttons to display in the message box.</param>
    /// <param name="title">The title text to display in the message box window. If null, a default title is used.</param>
    /// <param name="header">The header text to display above the message. If null, no header is shown.</param>
    /// <param name="icon">An optional icon to display in the message box. If null, no icon is shown.</param>
    /// <param name="windowOptions">Optional window options that control the appearance or behavior of the message box window. If null, default
    /// options are used.</param>
    /// <returns>A task that represents the asynchronous operation. The task result contains a value indicating which button the
    /// user clicked.</returns>
    /// <exception cref="InvalidOperationException">Thrown if the application is not running with a classic desktop style lifetime, or if there is no main window
    /// available.</exception>
    public static Task<AristeusMessageBoxResult> ShowDialogResult(string message, AristeusMessageBoxButtons buttons, string? title = null,
        string? header = null, AristeusMessageBoxIcons? icon = null, AristeusMessageBoxOptions? windowOptions = null)
    {
        if (Application.Current?.ApplicationLifetime is not IClassicDesktopStyleApplicationLifetime desktop)
        {
            throw new InvalidOperationException("The application is not an instance of IClassicDesktopStyleApplicationLifetime.");
        }

        if (desktop.MainWindow is not null)
        {
            return ShowDialogResult(desktop.MainWindow, message, buttons, title, header, icon, windowOptions);
        }

        throw new InvalidOperationException("The application does not contain a main window.");

    }
    #endregion

    #region Events
    private static void WindowOnKeyUp(object sender, KeyEventArgs e)
    {
        if (sender is not Window window) return;
        if (e.Key == Key.Escape)
        {
            window.Close(AristeusMessageBoxResult.Close);
        }
    }

    /// <summary>
    /// Handles the closed event of the window to dispose events.
    /// </summary>
    /// <param name="sender"></param>
    /// <param name="e"></param>
    private static void WindowOnClosed(object sender, EventArgs e)
    {
        if (sender is not Window window) return;
        if (window.Tag is not AristeusMessageBoxHost host) return;
        window.KeyUp -= WindowOnKeyUp;
        window.Closed -= WindowOnClosed;

        var actionButtons = host.ActionButtonsSource;
        if (actionButtons is not null)
        {
            foreach (var button in actionButtons)
            {
                button.Click -= ActionButtonOnClick;
            }
        }

        // Unload the content to free resources and allow reuse of the host control
        window.Content = null;
    }

    /// <summary>
    /// Handles the click event of the action button to close the window.
    /// </summary>
    /// <param name="sender"></param>
    /// <param name="e"></param>
    private static async void ActionButtonOnClick(object sender, RoutedEventArgs e)
    {
        if (sender is not Button button) return;
        if (button.Tag is Window window)
        {
            window.Close();
            return;
        }
        if (button.Tag is not AristeusMessageBoxButtonTag buttonTag) return;
        if (buttonTag.Owner is null) return;

        buttonTag.Owner.IsEnabled = false; // Prevent multiple clicks and interactions
        if (buttonTag.Link is not null) await buttonTag.OpenLink();

        if (buttonTag.Result.HasValue)
        {
            buttonTag.Owner.Close(buttonTag.Result.Value);
        }
        else
        {
            buttonTag.Owner.Close(sender);
        }
    }
    #endregion
}
