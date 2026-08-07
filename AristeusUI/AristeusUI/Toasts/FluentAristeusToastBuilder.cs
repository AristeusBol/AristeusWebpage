using Avalonia.Controls.Notifications;
using AristeusUI.Enums;

namespace AristeusUI.Toasts;

public static class FluentAristeusToastBuilder
{
    #region Content

    /// <summary>
    /// Creates a <see cref="AristeusToastBuilder"/> instance that can be used to construct a <see cref="IAristeusToast"/>
    /// </summary>
    public static AristeusToastBuilder CreateToast(this IAristeusToastManager manager) => new(manager);

    /// <summary>
    /// Creates a simple informational toast that can be dismissed by clicking and is otherwise dismissed after 3 seconds.
    /// This doesn't set the title/content and you should use <see cref="WithTitle"/> and <see cref="WithContent"/>
    /// </summary>
    public static AristeusToastBuilder CreateSimpleInfoToast(this IAristeusToastManager manager)
    {
        return new AristeusToastBuilder(manager)
            .OfType(NotificationType.Information)
            .Dismiss().After(TimeSpan.FromSeconds(3))
            .Dismiss().ByClicking();
    }

    /// <summary>
    /// Gives the toast a title.
    /// </summary>
    public static AristeusToastBuilder WithTitle(this AristeusToastBuilder builder, string title)
    {
        builder.SetTitle(title);
        return builder;
    }


    /// <summary>
    /// Show a loading Toast.
    /// </summary>
    public static AristeusToastBuilder WithLoadingState(this AristeusToastBuilder builder, bool state)
    {
        builder.SetLoadingState(state);
        return builder;
    }

    /// <summary>
    /// Gives the toast some content. This can be a ViewModel if desired - View will be located via the default location strategy.
    /// </summary>
    public static AristeusToastBuilder WithContent(this AristeusToastBuilder builder, object? content)
    {
        builder.SetContent(content);
        return builder;
    }

    /// <summary>
    /// Sets the notification type - By default it is <see cref="NotificationType.Information"/>
    /// </summary>
    public static AristeusToastBuilder OfType(this AristeusToastBuilder builder, NotificationType type)
    {
        builder.SetType(type);
        return builder;
    }

    #endregion

    #region Dismissing

    /// <summary>
    /// Begins a dismiss statement for the toast - Follow this with something like <see cref="After"/>.
    /// </summary>
    public static AristeusToastBuilder.DismissToast Dismiss(this AristeusToastBuilder builder) => new(builder);

    /// <summary>
    /// Automatically dismisses the toast after the given amount of time.
    /// </summary>
    public static AristeusToastBuilder After(this AristeusToastBuilder.DismissToast dismiss, TimeSpan after, bool interruptWhileHover = true)
    {
        dismiss.Builder.SetDismissAfter(after, interruptWhileHover);
        return dismiss.Builder;
    }

    /// <summary>
    /// Allows the toast to be dismissed by clicking anywhere on the toast.
    /// </summary>
    public static AristeusToastBuilder ByClicking(this AristeusToastBuilder.DismissToast dismiss)
    {
        dismiss.Builder.SetCanDismissByClicking(true);
        return dismiss.Builder;
    }

    #endregion

    #region Actions

    /// <summary>
    /// The action provided will be called if the body of the toast is clicked.
    /// </summary>
    public static AristeusToastBuilder OnClicked(this AristeusToastBuilder builder, Action<IAristeusToast> action)
    {
        builder.SetOnClicked(action);
        return builder;
    }

    /// <summary>
    /// The action provided will be called when the toast is dismissed for any reason, including clicking.
    /// </summary>
    public static AristeusToastBuilder OnDismissed(this AristeusToastBuilder builder, Action<IAristeusToast, AristeusToastDismissSource> onDismissAction)
    {
        builder.SetOnDismiss(onDismissAction);
        return builder;
    }

    /// <summary>
    /// Adds an action button to the toast which will call the provided callback on click. Any number of buttons can be added to a toast.
    /// </summary>
    public static AristeusToastBuilder WithActionButton(this AristeusToastBuilder builder, object buttonContent, Action<IAristeusToast> onClicked, bool dismissOnClick = false, AristeusButtonStyles style = AristeusButtonStyles.Flat)
    {
        builder.AddActionButton(buttonContent, onClicked, dismissOnClick, style);
        return builder;
    }

    #endregion
}