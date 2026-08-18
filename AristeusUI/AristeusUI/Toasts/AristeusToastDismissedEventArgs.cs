using System;

namespace AristeusUI.Toasts
{
    public class AristeusToastDismissedEventArgs : EventArgs
    {
        public IAristeusToast Toast { get; init; }

        public AristeusToastDismissSource DismissSource { get; init; }

        public AristeusToastDismissedEventArgs(IAristeusToast toast, AristeusToastDismissSource dismissSource)
        {
            Toast = toast;
            DismissSource = dismissSource;
        }
    }

    public delegate void AristeusToastDismissedEventHandler(object sender, AristeusToastDismissedEventArgs args);
}