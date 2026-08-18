using System.ComponentModel;
using System.Reflection;

namespace AristeusUI.Controls
{
    public sealed class DoubleViewModel : PropertyViewModelBase<double?>
    {
        public DoubleViewModel(INotifyPropertyChanged viewmodel, string displayName, PropertyInfo propertyInfo)
            : base(viewmodel, displayName, propertyInfo)
        {
        }
    }
}