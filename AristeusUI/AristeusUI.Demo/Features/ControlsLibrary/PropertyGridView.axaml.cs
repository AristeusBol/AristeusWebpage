using Avalonia.Controls;
using Avalonia.Controls.Primitives;
using Avalonia.Interactivity;
using AristeusUI.Controls;

namespace AristeusUI.Demo.Features.ControlsLibrary;

public partial class PropertyGridView : UserControl
{
    public PropertyGridView()
    {
        InitializeComponent();
    }

    private void ToggleButton_OnIsCheckedChanged(object? sender, RoutedEventArgs e)
    {
        if (sender is not ToggleButton toggleButton)
        {
            return;
        }

        var resource = this.FindResource("PropertyGridTemplateSelector");
        if (resource is PropertyGridTemplateSelector templateSelector)
        {
            templateSelector.UseAristeusHost = toggleButton.IsChecked == true;
        }
    }
}