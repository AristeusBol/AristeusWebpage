using CommunityToolkit.Mvvm.Input;
using Material.Icons;
using AristeusUI.Controls;
using AristeusUI.Toasts;

namespace AristeusUI.Demo.Features.ControlsLibrary;

public partial class ContextMenusViewModel(IAristeusToastManager toastManager) : DemoPageBase("Context Menus", MaterialIconKind.Menu)
{
    [RelayCommand]
    private void OptionClicked(bool withIcon)
    {
        toastManager.CreateSimpleInfoToast()
            .WithTitle("Clicked Context Menu")
            .WithContent(withIcon ? "You clicked the option with the icon." : "You clicked the option without the icon.")
            .Queue();
    }

    [RelayCommand]
    private void NestedOptionClicked()
    {
        toastManager.CreateSimpleInfoToast()
            .WithTitle("Clicked Context Menu")
            .WithContent("You clicked the nested option.")
            .Queue();
    }
}