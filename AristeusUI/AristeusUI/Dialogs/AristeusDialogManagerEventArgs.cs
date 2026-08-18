using System;

namespace AristeusUI.Dialogs
{
    public class AristeusDialogManagerEventArgs : EventArgs
    {
        public IAristeusDialog Dialog { get; set; }

        public AristeusDialogManagerEventArgs(IAristeusDialog dialog)
        {
            Dialog = dialog;
        }
    }
    
    public delegate void AristeusDialogManagerEventHandler(object sender, AristeusDialogManagerEventArgs args);
}