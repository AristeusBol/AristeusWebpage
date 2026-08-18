using CommunityToolkit.Mvvm.ComponentModel;
using Material.Icons;

namespace AristeusUI.Demo.Features.ControlsLibrary;

public partial class PropertyGridViewModel() : DemoPageBase("PropertyGrid", MaterialIconKind.Grid)
{
    [ObservableProperty] private FormViewModel? _form = new();
}