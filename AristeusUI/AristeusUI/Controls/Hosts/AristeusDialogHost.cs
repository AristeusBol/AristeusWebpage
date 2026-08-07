
using System;
using System.Threading.Tasks;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.Primitives;
using Avalonia.Rendering.Composition;
using AristeusUI.Dialogs;
using AristeusUI.Helpers;

namespace AristeusUI.Controls
{
    public class AristeusDialogHost : TemplatedControl
    {
        public static readonly StyledProperty<IAristeusDialogManager> ManagerProperty = AvaloniaProperty.Register<AristeusDialogHost, IAristeusDialogManager>(nameof(Manager));

        public IAristeusDialogManager Manager
        {
            get => GetValue(ManagerProperty);
            set => SetValue(ManagerProperty, value);
        }
        
        public static readonly StyledProperty<object?> DialogProperty = AvaloniaProperty.Register<AristeusDialogHost, object?>(nameof(Dialog));

        internal object? Dialog
        {
            get => GetValue(DialogProperty);
            set => SetValue(DialogProperty, value);
        }

        public static readonly StyledProperty<bool> IsDialogOpenProperty = AvaloniaProperty.Register<AristeusDialogHost, bool>(nameof(IsDialogOpen));

        internal bool IsDialogOpen
        {
            get => GetValue(IsDialogOpenProperty);
            set => SetValue(IsDialogOpenProperty, value);
        }

        protected override void OnApplyTemplate(TemplateAppliedEventArgs e)
        {
            base.OnApplyTemplate(e);
            if (e.NameScope.Find<Border>("PART_DialogBackground") is { } dialogBackground)
            {
                dialogBackground.PointerPressed += (_, _) => BackgroundRequestClose();
                dialogBackground.Loaded += (_, _) =>
                {
                    var v = ElementComposition.GetElementVisual(dialogBackground);
                    CompositionAnimationHelper.MakeOpacityAnimated(v, 400);
                }; 
            }
        }

        private void BackgroundRequestClose()
        {
            if (Dialog is not IAristeusDialog { CanDismissWithBackgroundClick: true } aristeusDialog) return;
            if (!aristeusDialog.CanDismissWithBackgroundClick) return;
            Manager.TryDismissDialog(aristeusDialog);
        }

        private static void OnManagerPropertyChanged(AvaloniaObject sender,
            AvaloniaPropertyChangedEventArgs propChanged)
        {
            if (sender is not AristeusDialogHost host)
                throw new NullReferenceException("Dependency object is not of valid type " + nameof(AristeusDialogHost));
            if (propChanged.OldValue is IAristeusDialogManager oldManager)
                host.DetachManagerEvents(oldManager);
            if (propChanged.NewValue is IAristeusDialogManager newManager)
                host.AttachManagerEvents(newManager);
        }

        private void AttachManagerEvents(IAristeusDialogManager newManager)
        {
            newManager.OnDialogShown += ManagerOnDialogShown;
            newManager.OnDialogDismissed += ManagerOnDialogDismissed;
        }
        
        private void DetachManagerEvents(IAristeusDialogManager oldManager)
        {
            oldManager.OnDialogShown -= ManagerOnDialogShown;
            oldManager.OnDialogDismissed -= ManagerOnDialogDismissed;
        }

        private void ManagerOnDialogShown(object sender, AristeusDialogManagerEventArgs args)
        {
            Dialog = args.Dialog;
            IsDialogOpen = true;
        }
        
        private void ManagerOnDialogDismissed(object sender, AristeusDialogManagerEventArgs args)
        {
            IsDialogOpen = false;
            Task.Delay(500).ContinueWith(_ =>
            {
                if (Dialog != args.Dialog) return;
                Dialog = null;
            }, TaskScheduler.FromCurrentSynchronizationContext());
        }

        static AristeusDialogHost()
        {
            ManagerProperty.Changed.Subscribe(
                new Avalonia.Reactive.AnonymousObserver<AvaloniaPropertyChangedEventArgs<IAristeusDialogManager>>(x =>
                    OnManagerPropertyChanged(x.Sender, x)));
        }
    }
}