using System;
using System.Collections.ObjectModel;
using Avalonia;
using Avalonia.Controls.Primitives;
using Avalonia.Media;
using AristeusUI.Dialogs;

namespace AristeusUI.Controls
{
    public class AristeusDialog : TemplatedControl, IAristeusDialog
    {
        public static readonly StyledProperty<object?> ViewModelProperty = AvaloniaProperty.Register<AristeusDialog, object?>(nameof(ViewModel));

        public object? ViewModel
        {
            get => GetValue(ViewModelProperty);
            set => SetValue(ViewModelProperty, value);
        }

        public static readonly StyledProperty<string?> TitleProperty = AvaloniaProperty.Register<AristeusDialog, string?>(nameof(Title));

        public string? Title
        {
            get => GetValue(TitleProperty);
            set => SetValue(TitleProperty, value);
        }

        public static readonly StyledProperty<object?> ContentProperty = AvaloniaProperty.Register<AristeusDialog, object?>(nameof(Content));

        public object? Content
        {
            get => GetValue(ContentProperty);
            set => SetValue(ContentProperty, value);
        }

        public static readonly StyledProperty<bool> IsViewModelOnlyProperty = AvaloniaProperty.Register<AristeusDialog, bool>(nameof(IsViewModelOnly));

        public bool IsViewModelOnly
        {
            get => GetValue(IsViewModelOnlyProperty);
            set => SetValue(IsViewModelOnlyProperty, value);
        }

        public static readonly StyledProperty<object?> IconProperty = AvaloniaProperty.Register<AristeusDialog, object?>(nameof(Icon));

        public object? Icon
        {
            get => GetValue(IconProperty);
            set => SetValue(IconProperty, value);
        }

        public static readonly StyledProperty<bool> ShowCardBackgroundProperty = AvaloniaProperty.Register<AristeusDialog, bool>(nameof(ShowCardBackground), defaultValue: true);

        public bool ShowCardBackground
        {
            get => GetValue(ShowCardBackgroundProperty);
            set => SetValue(ShowCardBackgroundProperty, value);
        }
        
        public static readonly StyledProperty<IBrush?> IconColorProperty = AvaloniaProperty.Register<AristeusDialog, IBrush?>(nameof(IconColor));

        public IBrush? IconColor
        {
            get => GetValue(IconColorProperty);
            set => SetValue(IconColorProperty, value);
        }

        public static readonly StyledProperty<ObservableCollection<object>> ActionButtonsProperty = AvaloniaProperty.Register<AristeusDialog, ObservableCollection<object>>(nameof(ActionButtons));

        public ObservableCollection<object> ActionButtons
        {
            get => GetValue(ActionButtonsProperty);
            set => SetValue(ActionButtonsProperty, value);
        }
        
        public IAristeusDialogManager? Manager { get; set; }
        
        public Action<IAristeusDialog>? OnDismissed { get; set; }

        public bool CanDismissWithBackgroundClick { get; set; }
        
        public AristeusDialog()
        {
            ActionButtons = [];
        }
        
        public void Dismiss() => Manager?.TryDismissDialog(this);

        public void ResetToDefault()
        {
            ActionButtons.Clear();
            ViewModel = null;
            Title = null;
            Content = null;
            IsViewModelOnly = false;
        }
    }
}