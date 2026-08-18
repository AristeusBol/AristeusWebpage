using Avalonia.Controls;
using Avalonia.Interactivity;
using AristeusUI.Controls;
using AristeusUI.Extensions;

namespace AristeusUI.Demo.Features.ControlsLibrary.Dialogs;

public partial class ToolWindow : AristeusWindow
{

    public ToolWindow()
    {
        InitializeComponent();
    }

    private void CenterOnScreenButton_OnClick(object? sender, RoutedEventArgs e)
    {
        this.CenterOnScreen();
    }

    private void ToggleAutoWindowSize_OnClick(object? sender, RoutedEventArgs e)
    {
        if (SizeToContent == SizeToContent.Manual)
        {
            SizeToContent = SizeToContent.WidthAndHeight;
            CanResize = false;
            CanMaximize = false;
            CanFullScreen = false;
        }
        else
        {
            SizeToContent = SizeToContent.Manual;
            CanResize = true;
            CanMaximize = true;
            CanFullScreen = true;
        }
    }
}