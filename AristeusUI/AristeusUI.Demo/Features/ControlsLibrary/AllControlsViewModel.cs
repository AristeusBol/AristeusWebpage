using CommunityToolkit.Mvvm.ComponentModel;
using Material.Icons;
using AristeusUI.Demo.Features;
using AristeusUI.Dialogs;

namespace AristeusUI.Demo.Features.ControlsLibrary;

public partial class AllControlsViewModel : DemoPageBase
{
    [ObservableProperty] private IAristeusDialogManager dialogManager;
    public AllControlsViewModel(IAristeusDialogManager dialogManager) : base("All Controls", MaterialIconKind.ViewDashboard, 100)
    {
        DialogManager = dialogManager;
    }
}
