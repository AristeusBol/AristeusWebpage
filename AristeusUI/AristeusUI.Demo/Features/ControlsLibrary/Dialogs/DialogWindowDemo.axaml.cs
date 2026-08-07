using Avalonia.Interactivity;
using AristeusUI.Controls;
using AristeusUI.Dialogs;

namespace AristeusUI.Demo.Features.ControlsLibrary.Dialogs;

public partial class DialogWindowDemo : AristeusWindow
{
    private readonly IAristeusDialogManager _mainWindowManager;
    private readonly IAristeusDialogManager _thisWindowManager = new AristeusDialogManager();
    
    public DialogWindowDemo(IAristeusDialogManager mainWindowManager)
    {
        _mainWindowManager = mainWindowManager;
        InitializeComponent();
        DialogHost.Manager = _thisWindowManager;
    }

    private void ShowDialogInThisWindowClicked(object? sender, RoutedEventArgs e)
    {
        _thisWindowManager.CreateDialog()
            .WithTitle("Dialog Demo")
            .WithContent("This dialog is shown in this window.\r\nClick outside the dialog or click dismiss to dismiss this dialog.")
            .Dismiss().ByClickingBackground()
            .WithActionButton("Dismiss", _ => {}, true)
            .TryShow();
    }

    private void ShowDialogInMainWindowClicked(object? sender, RoutedEventArgs e)
    {
        _mainWindowManager.CreateDialog()
            .WithTitle("Dialog Demo")
            .WithContent("This dialog is shown in the main window from the opened window.\r\nClick outside the dialog or click dismiss to dismiss this dialog.")
            .Dismiss().ByClickingBackground()
            .WithActionButton("Dismiss", _ => {}, true)
            .TryShow();
    }
    private void ShowDialogInBothWindowsClicked(object? sender, RoutedEventArgs e)
    {
        _mainWindowManager.CreateDialog()
            .WithTitle("Dialog Demo")
            .WithContent("This dialog is shown in both windows.\r\nClick outside the dialog or click dismiss to dismiss this dialog.")
            .Dismiss().ByClickingBackground()
            .WithActionButton("Dismiss", _ => {}, true)
            .TryShow();
        _thisWindowManager.CreateDialog()
            .WithTitle("Dialog Demo")
            .WithContent("This dialog is shown in both windows.\r\nClick outside the dialog or click dismiss to dismiss this dialog.")
            .Dismiss().ByClickingBackground()
            .WithActionButton("Dismiss", _ => {}, true)
            .TryShow();
    }
}