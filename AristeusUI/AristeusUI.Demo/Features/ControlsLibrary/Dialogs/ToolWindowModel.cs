using CommunityToolkit.Mvvm.ComponentModel;

namespace AristeusUI.Demo.Features.ControlsLibrary.Dialogs;

public partial class ToolWindowModel : ObservableObject
{
    [ObservableProperty]
    private double _maxWidthScreenRatio;

    [ObservableProperty]
    private double _maxHeightScreenRatio;

    [ObservableProperty]
    private bool _canResize;

    [ObservableProperty]
    private bool _canMaximize;

    [ObservableProperty]
    private string _header = string.Empty;

    [ObservableProperty]
    private string _message = string.Empty;
}