using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.Notifications;
using AristeusUI.ColorTheme;
using AristeusUI.Content;
using AristeusUI.Enums;
using AristeusUI.Extensions;
using AristeusUI.Helpers;

namespace AristeusUI.Toasts;

public class AristeusToastBuilder
{
    public IAristeusToastManager Manager { get; }
    public IAristeusToast Toast { get; }

    public AristeusToastBuilder(IAristeusToastManager manager)
    {
        Manager = manager;
        Toast = ToastPool.Get();
        Toast.Manager = Manager;
    }

    public IAristeusToast Queue()
    {
        Manager.Queue(Toast);
        return Toast;
    }

    public void SetTitle(string title) => Toast.Title = title;

    public void SetContent(object? content) => Toast.Content = content;

    public void SetCanDismissByClicking(bool canDismiss) => Toast.CanDismissByClicking = canDismiss;
    public void SetLoadingState(bool loading) => Toast.LoadingState = loading;

    public void SetType(NotificationType type)
    {
        Toast.Icon = type switch
        {
            NotificationType.Information => Icons.InformationOutline,
            NotificationType.Success => Icons.Check,
            NotificationType.Warning => Icons.AlertOutline,
            NotificationType.Error => Icons.AlertOutline,
            _ => throw new ArgumentOutOfRangeException(nameof(type), type, null)
        };
        Toast.Foreground = type switch
        {
            NotificationType.Information => NotificationColor.InfoIconForeground,
            NotificationType.Success => NotificationColor.SuccessIconForeground,
            NotificationType.Warning => NotificationColor.WarningIconForeground,
            NotificationType.Error => NotificationColor.ErrorIconForeground,
            _ => throw new ArgumentOutOfRangeException(nameof(type), type, null)
        };
    }


    public void SetDismissAfter(TimeSpan delay, bool interruptWhileHover = true)
    {
        Toast.InterruptDismissTimerWhileHover = interruptWhileHover;
        Toast.CanDismissByTime = delay.TotalMilliseconds > 0;
        Toast.DismissTimeout = delay;
    }

    public void SetOnDismiss(Action<IAristeusToast, AristeusToastDismissSource> action) => Toast.OnDismissed = action;

    public void SetOnClicked(Action<IAristeusToast> action) => Toast.OnClicked = action;

    [Obsolete("Use the new AddActionButton overload and pass AristeusButtonStyles instead for cleaner control over the button style.")]
    public void AddActionButton(object buttonContent, Action<IAristeusToast> action, bool dismissOnClick, bool flatStyle)
    {
        AddActionButton(buttonContent, action, dismissOnClick, flatStyle ? AristeusButtonStyles.Flat : AristeusButtonStyles.Basic);
    }

    public void AddActionButton(object buttonContent, Action<IAristeusToast> action, bool dismissOnClick, AristeusButtonStyles style = AristeusButtonStyles.Flat)
    {
        if (buttonContent is not Button btn)
        {
            btn = new Button
            {
                Content = buttonContent,
                Margin = (style & AristeusButtonStyles.Basic) == AristeusButtonStyles.Basic
                    ? new Thickness(14, -3, 0, 2)
                    : new Thickness(14, 9, 0, 12),
            };

            var styles = style.GetSetFlagsIgnoring(AristeusButtonStyles.Standard)
                .Select(v => v.ToString());

            btn.Classes.AddRange(styles);
        }

        btn.Tag = (action, dismissOnClick);
        Toast.ActionButtons.Add(btn);
    }

    public class DismissToast
    {
        public AristeusToastBuilder Builder { get; }

        public DismissToast(AristeusToastBuilder builder)
        {
            Builder = builder;
        }
    }
}