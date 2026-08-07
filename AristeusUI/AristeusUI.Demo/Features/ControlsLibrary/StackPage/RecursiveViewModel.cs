using System;
using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using AristeusUI.Controls;

namespace AristeusUI.Demo.Features.ControlsLibrary.StackPage;

public partial class RecursiveViewModel(int index, Action<RecursiveViewModel> onRecurseClicked)
    : ObservableObject, IAristeusStackPageTitleProvider
{
    public string Title { get; } = $"Recursive {index}";

    [RelayCommand]
    private void Recurse() => 
        onRecurseClicked.Invoke(new RecursiveViewModel(index + 1, onRecurseClicked));
}