using System;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using Material.Icons;
using AristeusUI.Controls;
using System.Threading.Tasks;
using AristeusUI.Toasts;

namespace AristeusUI.Demo.Features.ControlsLibrary;

public partial class TextViewModel(IAristeusToastManager toastManager) : DemoPageBase("Text", MaterialIconKind.Text)
{
    private const string DefaultText = "Hello, World!";

    [ObservableProperty] private string _textBoxValue = DefaultText;
    [ObservableProperty] private string _textBlockValue = DefaultText;
    [ObservableProperty] private string _SelectableTextBlockValue = DefaultText;
    [ObservableProperty] private bool _hyperlinkVisited;

    [RelayCommand]
    private void HyperlinkClicked()
    {
        HyperlinkVisited = true;
        toastManager.CreateToast()
            .WithTitle("Clicked Hyperlink")
            .WithContent("You clicked the hyperlink on the Text page.")
            .Dismiss().After(TimeSpan.FromSeconds(5))
            .Dismiss().ByClicking()
            .Queue();
    }
}