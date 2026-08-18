using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Interactivity;
using AristeusUI.Controls;
using AristeusUI.Enums;
using AristeusUI.Models;
using System.Runtime.CompilerServices;

namespace AristeusUI.Demo;

public partial class AristeusUIDemoView : AristeusWindow
{
    public AristeusUIDemoView()
    {
        InitializeComponent();

        if (RuntimeFeature.IsDynamicCodeCompiled == false)
        {
            Title += " (native)";
        }
    }

    private void ThemeMenuItem_OnClick(object? sender, RoutedEventArgs e)
    {
        if (DataContext is not AristeusUIDemoViewModel vm) return;
        if (e.Source is not MenuItem mItem) return;
        if (mItem.DataContext is not AristeusColorTheme cTheme) return;
        vm.ChangeTheme(cTheme);
    }

    private void BackgroundMenuItem_OnClick(object? sender, RoutedEventArgs e)
    {
        if (DataContext is not AristeusUIDemoViewModel vm) return;
        if (e.Source is not MenuItem mItem) return;
        if (mItem.DataContext is not AristeusBackgroundStyle cStyle) return;
        vm.BackgroundStyle = cStyle;
    }

    private void InputElement_OnPointerPressed(object? sender, PointerPressedEventArgs e)
    {
        IsMenuVisible = !IsMenuVisible;
    }
}