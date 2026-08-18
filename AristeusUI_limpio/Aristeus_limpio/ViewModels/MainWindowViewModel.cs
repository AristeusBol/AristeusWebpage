using System.Collections.ObjectModel;

using CommunityToolkit.Mvvm.ComponentModel;

using SukiUI.Models;

using SukiUI.Controls;
// Asegúrate de importar el namespace de tus ViewModels si están en otra carpeta:
// using Aristeus_limpio.ViewModels; 

namespace Aristeus_limpio.ViewModels;

public partial class MainWindowViewModel : ObservableObject
{
    public ObservableCollection<SukiSideMenuItem> MenuItems { get; }

    public MainWindowViewModel()
    {
        MenuItems = new ObservableCollection<SukiSideMenuItem>
        {
            new SukiSideMenuItem
            {
                Header = "Grass-Gauge",
                PageContent = new GrassGaugeViewModel()
            },
            new SukiSideMenuItem
            {
                Header = "Cattle-Vision",
                PageContent = new CattleVisionViewModel()
            },
            new SukiSideMenuItem
            {
                Header = "Sentry-Ward",
                PageContent = new SentryWardViewModel()
            }
        };
    }
}