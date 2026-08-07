using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using AristeusUI.Controls;
using AristeusUI.Dialogs;

namespace AristeusUI.Demo.Features.Dashboard;

public partial class DialogViewModel(IAristeusDialog dialog) : ObservableObject
{
    [RelayCommand]
    private void CloseDialog()
    {
        dialog.Dismiss();
    }
}