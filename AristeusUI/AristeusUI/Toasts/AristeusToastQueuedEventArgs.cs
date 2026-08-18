namespace AristeusUI.Toasts;

public class AristeusToastQueuedEventArgs : EventArgs
{
    public IAristeusToast Toast { get; set; }

    public AristeusToastQueuedEventArgs(IAristeusToast toast)
    {
        Toast = toast;
    }
}

public delegate void AristeusToastQueuedEventHandler(object sender, AristeusToastQueuedEventArgs args);