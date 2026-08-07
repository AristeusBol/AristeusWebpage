using System;
using Avalonia;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Markup.Xaml.Styling;
using Avalonia.Media;
using Avalonia.Styling;
using AristeusUI.Controls;
using AristeusUI.Models;

namespace AristeusUI.Theme.Shadcn
{
    public static class Shadcn
    {
        public static void Configure(Application application, ThemeVariant startupTheme)
        {
            Application.Current.Resources.MergedDictionaries.Add(new ResourceInclude(new Uri("avares://AristeusUI/Theme/Shadcn/BlackWhiteTheme.axaml")
            )
            {
                Source = new Uri("avares://AristeusUI/Theme/Shadcn/BlackWhiteTheme.axaml")
            });
        
            var whiteTheme = new AristeusColorTheme("White", new Color(255, 255, 255, 255), new Color(255, 255, 255, 255));
            var blackTheme = new AristeusColorTheme("Black", new Color(255, 0, 0, 0), new Color(255, 0, 0, 0));

            AristeusTheme.GetInstance().AddColorThemes(new []{whiteTheme, blackTheme});

            var BlackStyles = new StyleInclude(new Uri("avares://AristeusUI/Theme/Shadcn/ShadDarkStyles.axaml"))
            {
                Source = new Uri("avares://AristeusUI/Theme/Shadcn/ShadDarkStyles.axaml")
            };

        
            AristeusTheme.GetInstance().OnBaseThemeChanged += variant =>
            {
                if (variant == ThemeVariant.Dark)
                {
                    application.Styles.Add(BlackStyles);
                    AristeusTheme.GetInstance().ChangeColorTheme(whiteTheme);
                
                }
                else
                {
                    AristeusTheme.GetInstance().ChangeColorTheme(blackTheme);
                    application.Styles.Remove(BlackStyles);
                }
            };

            try
            {
                ((AristeusWindow)((ClassicDesktopStyleApplicationLifetime)application.ApplicationLifetime).MainWindow)
                    .BackgroundShaderFile = "backgroundshadcn";
            }catch{}
            
            AristeusTheme.GetInstance().ChangeBaseTheme(ThemeVariant.Light);
            AristeusTheme.GetInstance().ChangeBaseTheme(ThemeVariant.Dark);
            AristeusTheme.GetInstance().ChangeBaseTheme(startupTheme);

        }
    }
}