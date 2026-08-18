using Avalonia.Controls;
using Avalonia.Threading;

namespace AristeusUI.Demo.Features.Splash;

public partial class SplashView : UserControl
{
    public SplashView()
    {
        AristeusTheme.GetInstance().OnBaseThemeChanged += _ =>
        {
            Dispatcher.UIThread.Post(() =>
            {
                TextBlockWithInline.InvalidateVisual();
            });
        };
        InitializeComponent();
    }
}