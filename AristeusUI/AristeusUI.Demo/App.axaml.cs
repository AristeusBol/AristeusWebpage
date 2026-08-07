using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Markup.Xaml;
using Avalonia.Media;
using Microsoft.Extensions.DependencyInjection;
using AristeusUI.Controls;
using AristeusUI.Demo.Common;
using AristeusUI.Demo.Features.ControlsLibrary;
using AristeusUI.Demo.Features.ControlsLibrary.Colors;
using AristeusUI.Demo.Features.ControlsLibrary.Dialogs;
using AristeusUI.Demo.Features.ControlsLibrary.DockControls;
using AristeusUI.Demo.Features.ControlsLibrary.StackPage;
using AristeusUI.Demo.Features.ControlsLibrary.TabControl;
using AristeusUI.Demo.Features.ControlsLibrary.Toasts;
using AristeusUI.Demo.Features.CustomTheme;
using AristeusUI.Demo.Features.Dashboard;
using AristeusUI.Demo.Features.Effects;
using AristeusUI.Demo.Features.Helpers;
using AristeusUI.Demo.Features.Playground;
using AristeusUI.Demo.Features.Splash;
using AristeusUI.Demo.Features.Theming;
using AristeusUI.Demo.Services;
using AristeusUI.Dialogs;
using AristeusUI.Enums;
using AristeusUI.Toasts;

namespace AristeusUI.Demo;

public class App : Application
{
    
    public static AristeusDialogManager SingleViewDialogManager { get; set; } 
        
    public override void Initialize()
    {
        AvaloniaXamlLoader.Load(this);
    }

    public override void OnFrameworkInitializationCompleted()
    {

        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            var services = new ServiceCollection();
            services.AddSingleton(desktop);
            var views = ConfigureViews(services);
            var provider = ConfigureServices(services);
            DataTemplates.Add(new ViewLocator(views));
            desktop.MainWindow = views.CreateView<AristeusUIDemoViewModel>(provider) as Window;
        }
        else if (ApplicationLifetime is ISingleViewApplicationLifetime singleView)
        {
            var p = new Panel();
            p.Children.Add(new AristeusBackground(){Style = AristeusBackgroundStyle.Bubble});
            SingleViewDialogManager = new AristeusDialogManager();
            
            p.Children.Add(new AllControlsView(){DataContext = new AllControlsViewModel(SingleViewDialogManager)});
            
            singleView.MainView = new AristeusMainHost()
            {
                Hosts = [
                    new AristeusDialogHost
                    {
                        Manager = SingleViewDialogManager
                    }
                ],
                Content =  p
            };
        }

        base.OnFrameworkInitializationCompleted();

    //    Shadcn.Configure(Application.Current, ThemeVariant.Dark);
    }

    private static AristeusViews ConfigureViews(ServiceCollection services)
    {
        return new AristeusViews()

            // Add main view
            .AddView<AristeusUIDemoView, AristeusUIDemoViewModel>(services)

            // Add pages
            .AddView<SplashView, SplashViewModel>(services)
            .AddView<ThemingView, ThemingViewModel>(services)
            .AddView<PlaygroundView, PlaygroundViewModel>(services)
            .AddView<EffectsView, EffectsViewModel>(services)
            .AddView<DashboardView, DashboardViewModel>(services)
            .AddView<ButtonsView, ButtonsViewModel>(services)
            .AddView<CardsView, CardsViewModel>(services)
            .AddView<CollectionsView, CollectionsViewModel>(services)
            .AddView<ContextMenusView, ContextMenusViewModel>(services)
            .AddView<DockView, DockViewModel>(services)
            .AddView<DockMvvmView, DockMvvmViewModel>(services)
            .AddView<ExpanderView, ExpanderViewModel>(services)
            .AddView<IconsView, IconsViewModel>(services)
            .AddView<InfoBarView, InfoBarViewModel>(services)
            .AddView<MiscView, MiscViewModel>(services)
            .AddView<ProgressView, ProgressViewModel>(services)
            .AddView<PropertyGridView, PropertyGridViewModel>(services)
            .AddView<TextView, TextViewModel>(services)
            .AddView<TogglesView, TogglesViewModel>(services)
            .AddView<ToastsView, ToastsViewModel>(services)
            .AddView<TabControlView, TabControlViewModel>(services)
            .AddView<StackPageView, StackPageViewModel>(services)
            .AddView<DialogsView, DialogsViewModel>(services)
            .AddView<HelpersView, HelpersViewModel>(services)
            .AddView<ColorsView, ColorsViewModel>(services)
            .AddView<ExperimentalView, ExperimentalViewModel>(services)
            .AddView<AllControlsView, AllControlsViewModel>(services)

            // Add docks view for DockMvvvm
            .AddView<DocumentText, DocumentTextViewModel>(services)
            .AddView<ErrorList, ErrorListViewModel>(services)
            .AddView<OutputView, OutputViewModel>(services)
            .AddView<PropertiesView, PropertiesViewModel>(services)
            .AddView<SolutionExplore, SolutionExploreViewModel>(services)

            // Add additional views
            .AddView<DialogView, DialogViewModel>(services)
            .AddView<VmDialogView, VmDialogViewModel>(services)
            .AddView<RecursiveView, RecursiveViewModel>(services)
            .AddView<CustomThemeDialogView, CustomThemeDialogViewModel>(services);
    }

    private static ServiceProvider ConfigureServices(ServiceCollection services)
    {
        services.AddSingleton<ClipboardService>();
        services.AddSingleton<PageNavigationService>();
        services.AddSingleton<IAristeusToastManager, AristeusToastManager>();
        services.AddSingleton<IAristeusDialogManager, AristeusDialogManager>();

        return services.BuildServiceProvider();
    }
}
