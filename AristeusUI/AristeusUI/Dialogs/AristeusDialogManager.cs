using AristeusUI.Helpers;

namespace AristeusUI.Dialogs
{
    public class AristeusDialogManager : IAristeusDialogManager
    {
        public event AristeusDialogManagerEventHandler? OnDialogShown;
        public event AristeusDialogManagerEventHandler? OnDialogDismissed;

        private IAristeusDialog? _activeDialog;
        
        public bool TryShowDialog(IAristeusDialog dialog)
        {
            if (_activeDialog != null) return false;
            _activeDialog = dialog;
            OnDialogShown?.Invoke(this, new AristeusDialogManagerEventArgs(_activeDialog));
            return true;
        }

        public bool TryDismissDialog(IAristeusDialog dialog)
        {
            if (_activeDialog == null || _activeDialog != dialog) 
                return false;

            var dismissedDialog = _activeDialog;
            _activeDialog = null;
            OnDialogDismissed?.Invoke(this, new AristeusDialogManagerEventArgs(dismissedDialog));
            dismissedDialog.OnDismissed?.Invoke(dismissedDialog);

            return true;
        }

        public void DismissDialog()
        {
            if (_activeDialog == null) 
                return;

            var dismissedDialog = _activeDialog;
            _activeDialog = null;
            OnDialogDismissed?.Invoke(this, new AristeusDialogManagerEventArgs(dismissedDialog));
            dismissedDialog.OnDismissed?.Invoke(dismissedDialog);
        }
    }
}