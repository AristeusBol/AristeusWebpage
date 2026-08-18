using System.ComponentModel;
using System.Reflection;

namespace AristeusUI.Controls
{
    public sealed class DecimalViewModel : PropertyViewModelBase<decimal?>
    {
        public DecimalViewModel(INotifyPropertyChanged viewmodel, string displayName, PropertyInfo propertyInfo)
            : base(viewmodel, displayName, propertyInfo)
        {
        }
    }
}