using System.Collections.ObjectModel;
using Avalonia.Media;

namespace AristeusUI.Toasts;

public interface IAristeusToast
{
    IAristeusToastManager? Manager { get; set; }
    double DismissStartTimestamp { get; set; }
    string Title { get; set; }
    object? Content { get; set; }
    object? Icon { get; set; }
    IBrush? Foreground { get; set; }
    bool CanDismissByClicking { get; set; }
    bool CanDismissByTime { get; set; }
    bool InterruptDismissTimerWhileHover { get; set; }
    TimeSpan DismissTimeout { get; set; }
    double DismissProgressValue { get; set; }
    bool LoadingState { get; set; }
    Action<IAristeusToast, AristeusToastDismissSource>? OnDismissed { get; set; }
    Action<IAristeusToast>? OnClicked { get; set; }
    ObservableCollection<object> ActionButtons { get; }
    void AnimateShow();
    void AnimateDismiss();
    IAristeusToast ResetToDefault();

}