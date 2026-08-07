using Avalonia.Controls;
using Avalonia.Data.Converters;
using AristeusUI.Controls;
using System.Globalization;

namespace AristeusUI.Converters
{
    public class ProgressToContentConverter : IValueConverter
    {
        public static readonly ProgressToContentConverter Instance = new ProgressToContentConverter();

        public object? Convert(object? value, Type targetType, object? parameter, CultureInfo culture)
        {
            if (value is bool booleanValue && booleanValue == true) {
                return new Loading() { LoadingStyle = LoadingStyle.Simple };
            }
            return new Panel();
        }

        public object ConvertBack(object? value, Type targetType,
            object? parameter, CultureInfo culture)
        {
            throw new NotSupportedException();
        }
    }
}