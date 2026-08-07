using System.ComponentModel;
using System.Reflection;

namespace AristeusUI.Controls
{
    public sealed class IntegerViewModel : PropertyViewModelBase<int?>
    {
        public IntegerViewModel(INotifyPropertyChanged viewmodel, string displayName, PropertyInfo propertyInfo)
            : base(viewmodel, displayName, propertyInfo)
        {
        }
    }
}