using System.ComponentModel;

namespace AristeusUI.Controls
{
    public interface IPropertyViewModel : INotifyPropertyChanged, IDisposable
    {
        string DisplayName { get; }
        bool IsReadOnly { get; }
        object? Value { get; set; }
    }
}