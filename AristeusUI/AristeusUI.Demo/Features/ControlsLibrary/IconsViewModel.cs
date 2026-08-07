using Avalonia.Media;
using Material.Icons;
using AristeusUI.Content;
using AristeusUI.Demo.Services;
using AristeusUI.Toasts;
using System.Collections.Generic;
using System.Reflection;

namespace AristeusUI.Demo.Features.ControlsLibrary;

public partial class IconsViewModel : DemoPageBase
{
    public IEnumerable<IconItemViewModel> Icons { get; }

    public IconsViewModel(ClipboardService clipboardService, IAristeusToastManager toastManager) : base("Icons", MaterialIconKind.AlphaICircleOutline, int.MaxValue)
    {
        var fields = typeof(Icons).GetFields(BindingFlags.Public | BindingFlags.Static);

        var icons = new List<IconItemViewModel>(fields.Length);

        foreach (var field in fields)
        {
            if (field.GetValue(null) is not Geometry geometry)
            {
                continue;
            }

            var icon = new IconItemViewModel(clipboardService, toastManager)
            {
                Name = field.Name,
                Geometry = geometry
            };

            icons.Add(icon);
        }

        Icons = icons;
    }
}