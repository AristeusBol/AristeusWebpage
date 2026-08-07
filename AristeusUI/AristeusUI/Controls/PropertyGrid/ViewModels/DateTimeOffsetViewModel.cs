using System;
using System.ComponentModel;
using System.Reflection;

namespace AristeusUI.Controls
{
    public sealed class DateTimeOffsetViewModel : PropertyViewModelBase<DateTimeOffset?>
    {
        public DateTimeOffsetViewModel(INotifyPropertyChanged viewmodel, string displayName, PropertyInfo propertyInfo)
            : base(viewmodel, displayName, propertyInfo)
        {
        }
    }
}