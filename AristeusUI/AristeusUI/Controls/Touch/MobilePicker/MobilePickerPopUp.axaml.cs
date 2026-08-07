using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Markup.Xaml;
using AristeusUI.Dialogs;

namespace AristeusUI.Controls.Touch.MobilePicker;

public partial class MobilePickerPopUp : UserControl
{
    private IAristeusDialogManager? dialogManager;

    public MobilePickerPopUp()
    {
        InitializeComponent();
    }

    public MobilePickerPopUp(IAristeusDialogManager manager)
    {
        InitializeComponent();
        dialogManager = manager;

    }

    private void InitializeComponent()
    {
        AvaloniaXamlLoader.Load(this);
    }

    private void DoneClick(object sender, RoutedEventArgs e)
    {
        dialogManager?.DismissDialog();
        var model = ((MobilePickerPopUpViewModel)DataContext);

        model.mobilePicker.SelectedItem = model.SelectedItem;

    }
}
