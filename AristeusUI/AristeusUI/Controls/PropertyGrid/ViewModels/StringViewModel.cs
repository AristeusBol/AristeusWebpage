using System.ComponentModel;
using System.Reflection;

namespace AristeusUI.Controls
{
    public sealed class StringViewModel : PropertyViewModelBase<string?>
    {
        public StringViewModel(INotifyPropertyChanged viewmodel, string displayName, PropertyInfo propertyInfo)
            : base(viewmodel, displayName, propertyInfo)
        {
        }
    }
}