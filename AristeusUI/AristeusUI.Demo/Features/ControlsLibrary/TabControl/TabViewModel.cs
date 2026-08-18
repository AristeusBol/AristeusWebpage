using CommunityToolkit.Mvvm.ComponentModel;

namespace AristeusUI.Demo.Features.ControlsLibrary.TabControl;

public class TabViewModel(int index, bool isEnabled = true) : ObservableObject
{
    public string Header { get; } = $"Tab {index}";
    public string Content { get; } = $"Tab {index} Content.";
    public bool IsEnabled { get; } = isEnabled;
}