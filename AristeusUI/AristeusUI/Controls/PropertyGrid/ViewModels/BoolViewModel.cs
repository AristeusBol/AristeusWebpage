using System.ComponentModel;
using System.Reflection;

namespace AristeusUI.Controls
{
    public sealed class BoolViewModel : PropertyViewModelBase<bool?>
    {
        public BoolViewModel(INotifyPropertyChanged viewmodel, string displayName, PropertyInfo propertyInfo)
            : base(viewmodel, displayName, propertyInfo)
        {
        }
    }
}