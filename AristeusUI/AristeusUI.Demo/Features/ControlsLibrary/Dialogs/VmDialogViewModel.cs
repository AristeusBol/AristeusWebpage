using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using AristeusUI.Dialogs;

namespace AristeusUI.Demo.Features.ControlsLibrary.Dialogs;

public partial class VmDialogViewModel(IAristeusDialog dialog) : ObservableObject
{
    [RelayCommand]
    private void CloseDialog() => dialog.Dismiss();
}