using Avalonia.Interactivity;
using AristeusUI.Controls;
using AristeusUI.Toasts;

namespace AristeusUI.Demo.Features.ControlsLibrary.Toasts
{
    public partial class ToastWindowDemo : AristeusWindow
    {
        private readonly IAristeusToastManager _thisWindowManager = new AristeusToastManager();
        private readonly IAristeusToastManager _mainWindowManager;
        
        public ToastWindowDemo(IAristeusToastManager mainWindowManager)
        {
            _mainWindowManager = mainWindowManager;
            InitializeComponent();
            ToastHost.Manager = _thisWindowManager;
        }

        private void ShowToastInThisWindowClicked(object? sender, RoutedEventArgs e)
        {
            _thisWindowManager.CreateSimpleInfoToast()
                .WithTitle("Window Toast")
                .WithContent("Toast shown in the opened window.")
                .Queue();
        }

        private void ShowToastInMainWindowClicked(object? sender, RoutedEventArgs e)
        {
            _mainWindowManager.CreateSimpleInfoToast()
                .WithTitle("Main Window Toast")
                .WithContent("Toast shown in the main window from the opened window.")
                .Queue();
        }

        private void ShowToastInBothWindowsClicked(object? sender, RoutedEventArgs e)
        {
            // You could quite easily share a `IAristeusToastManager` instance if you wanted to this.
            _mainWindowManager.CreateSimpleInfoToast()
                .WithTitle("Both Windows Toast")
                .WithContent("Toast shown in both windows from the opened window.")
                .Queue();
            _thisWindowManager.CreateSimpleInfoToast()
                .WithTitle("Both Windows Toast")
                .WithContent("Toast shown in both windows from the opened window.")
                .Queue();
        }
    }
}