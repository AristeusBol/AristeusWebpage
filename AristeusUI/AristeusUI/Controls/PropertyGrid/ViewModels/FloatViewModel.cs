using System.ComponentModel;
using System.Reflection;

namespace AristeusUI.Controls
{
    public sealed class FloatViewModel : PropertyViewModelBase<float?>
    {
        public FloatViewModel(INotifyPropertyChanged viewmodel, string displayName, PropertyInfo propertyInfo)
            : base(viewmodel, displayName, propertyInfo)
        {
        }
    }
}