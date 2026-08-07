using Avalonia.Controls;
using Avalonia.Media;
using AristeusUI.Content;

namespace AristeusUI.MessageBox;

/// <summary>
/// Factory for creating icons for the message box.
/// </summary>
public static class AristeusMessageBoxIconsFactory
{
    public static PathIcon CreateIcon(double size = double.NaN)
    {
        return new PathIcon
        {
            Width = size,
            Height = size,
        };
    }

    public static PathIcon CreateIcon(AristeusMessageBoxIcons icon, double size = double.NaN)
    {
        var pathIcon = CreateIcon(size);
        pathIcon.Tag = icon;

        switch (icon)
        {
            case AristeusMessageBoxIcons.Question:
            {
                pathIcon.Data = Icons.CircleHelp;
                /*if (Application.Current!.TryGetResource("AristeusInformationColor", Application.Current.ActualThemeVariant, out var value))
                {
                    pathIcon.Foreground = value is Color color ? new ImmutableSolidColorBrush(color) : Brushes.CornflowerBlue;
                }
                else
                {
                    pathIcon.Foreground = Brushes.CornflowerBlue;
                }*/
                pathIcon.Foreground = Brushes.CornflowerBlue;
                break;
            }
            case AristeusMessageBoxIcons.Information:
                pathIcon.Data = Icons.CircleInformation;
                pathIcon.Foreground = Brushes.CornflowerBlue;
                break;
            case AristeusMessageBoxIcons.Exclamation:
                pathIcon.Data = Icons.CircleWarning;
                pathIcon.Foreground = Brushes.Gold;
                break;
            case AristeusMessageBoxIcons.Warning:
            {
                pathIcon.Data = Icons.TriangleAlert;
                pathIcon.Foreground = Brushes.Gold;
                /*if (Application.Current!.TryGetResource("AristeusWarningColor", Application.Current.ActualThemeVariant, out var value))
                {
                    pathIcon.Foreground = value is Color color ? new ImmutableSolidColorBrush(color) : Brushes.Gold;
                }
                else
                {
                    pathIcon.Foreground = Brushes.Gold;
                }*/
                break;
            }
            case AristeusMessageBoxIcons.Error:
                pathIcon.Data = Icons.CircleClose;
                pathIcon.Foreground = Brushes.Firebrick;
                break;
            case AristeusMessageBoxIcons.Success:
            {
                pathIcon.Data = Icons.CircleCheck;
                pathIcon.Foreground = Brushes.ForestGreen;
                break;
            }
            case AristeusMessageBoxIcons.Star:
            {
                pathIcon.Data = Icons.Star;
                pathIcon.Foreground = Brushes.Gold;
                break;
            }
            default:
                throw new ArgumentOutOfRangeException(nameof(icon), icon, null);
        }

        return pathIcon;
    }
}