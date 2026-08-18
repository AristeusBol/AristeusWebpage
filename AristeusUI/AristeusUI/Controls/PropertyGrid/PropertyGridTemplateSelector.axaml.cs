using System.Linq;
using System.Threading.Tasks;
using Avalonia.Controls;
using Avalonia.Controls.Templates;
using Avalonia.Interactivity;
using Avalonia.Markup.Xaml;
using Avalonia.VisualTree;
using AristeusUI.Dialogs;

namespace AristeusUI.Controls;

public partial class PropertyGridTemplateSelector : ResourceDictionary, IDataTemplate
{
    public AristeusDialogHost? AristeusDialogHost { get; set; }

    public bool UseAristeusHost { get; set; } = true;

    public PropertyGridTemplateSelector()
    {
        InitializeComponent();
    }

    private void InitializeComponent()
    {
        AvaloniaXamlLoader.Load(this);
    }

    public Control? Build(object? param)
    {
        if (param is null)
        {
            return null;
        }

        var type = param.GetType();
        var key = type.Name;

        if (TryGetResource(key, null, out var resource))
        {
            if (resource is IDataTemplate template)
            {
                return template.Build(param);
            }
        }

        return null;
    }

    public bool Match(object? data)
    {
        if (data is null)
        {
            return false;
        }

        var type = data.GetType();
        var key = type.Name;

        if (string.IsNullOrEmpty(key))
        {
            return false;
        }

        return ContainsKey(key) != false;
    }

    private static void ShowAristeusHostDialog(IAristeusDialogManager manager, ComplexTypeViewModel viewModel)
    {
        manager
            .CreateDialog()
            .WithContent(new PropertyGridDialog()
            {
                DataContext = viewModel.Value
            })
            .WithTitle(viewModel.DisplayName)
            .Dismiss().ByClickingBackground()
            .TryShow();
    }

    private static async Task ShowWindowDialogAsync(Control control)
    {
        var root = TopLevel.GetTopLevel(control);
        if (root is not Window parentWindow || control.DataContext is not ComplexTypeViewModel childViewModel || childViewModel.Value is null)
        {
            return;
        }

        var window = new PropertyGridWindow()
        {
            DataContext = childViewModel.Value,
            Title = childViewModel.DisplayName,
        };

        await window.ShowDialog(parentWindow);
    }

    protected virtual async void OnMoreInfoClick(object sender, RoutedEventArgs e)
    {
        if (sender is not Control control)
        {
            return;
        }

        var aristeusDialogHost = AristeusDialogHost;
        if (UseAristeusHost)
        {
            if (aristeusDialogHost is not null)
            {
                if (control.DataContext is not ComplexTypeViewModel childViewModel || childViewModel.Value is null)
                {
                    return;
                }

                ShowAristeusHostDialog(aristeusDialogHost.Manager, childViewModel);
            }
            else
            {
                var root = TopLevel.GetTopLevel(control);
                if (root is not AristeusWindow parentWindow || control.DataContext is not ComplexTypeViewModel childViewModel || childViewModel.Value is null)
                {
                    return;
                }

                aristeusDialogHost = parentWindow.Hosts.Where(p => p is AristeusDialogHost).Cast<AristeusDialogHost>().FirstOrDefault();
                if (aristeusDialogHost is not null)
                {
                    ShowAristeusHostDialog(aristeusDialogHost.Manager, childViewModel);
                }
                else
                {
                    await ShowWindowDialogAsync(control);
                }
            }
        }
        else
        {
            await ShowWindowDialogAsync(control);
        }
    }
}
