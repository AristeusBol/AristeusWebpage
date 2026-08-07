using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.Primitives;
using Avalonia.Layout;
using AristeusUI.Enums;
using AristeusUI.Helpers;
using AristeusUI.Toasts;

namespace AristeusUI.Controls
{
    public class AristeusToastHost : ItemsControl
    {
        public static readonly StyledProperty<IAristeusToastManager> ManagerProperty =
            AvaloniaProperty.Register<AristeusToastHost, IAristeusToastManager>(nameof(Manager));

        public IAristeusToastManager Manager
        {
            get => GetValue(ManagerProperty);
            set => SetValue(ManagerProperty, value);
        }

        public static readonly StyledProperty<byte> MaxToastsProperty = AvaloniaProperty.Register<AristeusToastHost, byte>(nameof(MaxToasts), defaultValue: 5);

        public byte MaxToasts
        {
            get => GetValue(MaxToastsProperty);
            set => SetValue(MaxToastsProperty, value);
        }

        public static readonly StyledProperty<ToastLocation> PositionProperty = AvaloniaProperty.Register<AristeusToastHost, ToastLocation>(nameof(Position), defaultValue: ToastLocation.BottomRight);

        public ToastLocation Position
        {
            get => GetValue(PositionProperty);
            set => SetValue(PositionProperty, value);
        }

        protected override void OnApplyTemplate(TemplateAppliedEventArgs e)
        {
            base.OnApplyTemplate(e);
            OnPositionChanged(Position);
        }

        protected override void OnPropertyChanged(AvaloniaPropertyChangedEventArgs change)
        {
            base.OnPropertyChanged(change);
            if (change.Property == PositionProperty && change.NewValue is ToastLocation loc)
                OnPositionChanged(loc);
        }

        private void OnPositionChanged(ToastLocation newLoc)
        {
            HorizontalAlignment = newLoc switch
            {
                ToastLocation.BottomRight => HorizontalAlignment.Right,
                ToastLocation.BottomLeft => HorizontalAlignment.Left,
                ToastLocation.TopRight => HorizontalAlignment.Right,
                ToastLocation.TopLeft => HorizontalAlignment.Left,
                _ => throw new ArgumentOutOfRangeException()
            };
            VerticalAlignment = newLoc switch
            {
                ToastLocation.BottomRight => VerticalAlignment.Bottom,
                ToastLocation.BottomLeft => VerticalAlignment.Bottom,
                ToastLocation.TopRight => VerticalAlignment.Top,
                ToastLocation.TopLeft => VerticalAlignment.Top,
                _ => throw new ArgumentOutOfRangeException()
            };
        }

        private static void OnManagerPropertyChanged(AvaloniaObject sender,
            AvaloniaPropertyChangedEventArgs propChanged)
        {
            if (sender is not AristeusToastHost host)
                throw new NullReferenceException("Dependency object is not of valid type " + nameof(AristeusToastHost));
            if (propChanged.OldValue is IAristeusToastManager oldManager)
                host.DetachManagerEvents(oldManager);
            if (propChanged.NewValue is IAristeusToastManager newManager)
                host.AttachManagerEvents(newManager);
        }

        private void AttachManagerEvents(IAristeusToastManager newManager)
        {
            newManager.OnToastQueued += ManagerOnToastQueued;
            newManager.OnToastDismissed += ManagerOnToastDismissed;
            newManager.OnAllToastsDismissed += ManagerOnAllToastsDismissed;
        }

        private void DetachManagerEvents(IAristeusToastManager oldManager)
        {
            oldManager.OnToastQueued -= ManagerOnToastQueued;
            oldManager.OnToastDismissed -= ManagerOnToastDismissed;
            oldManager.OnAllToastsDismissed -= ManagerOnAllToastsDismissed;
        }

        private void ManagerOnToastDismissed(object sender, AristeusToastDismissedEventArgs args) =>
            ClearToast(args.Toast);

        private void ManagerOnAllToastsDismissed(object sender, EventArgs e)
        {
            foreach(var toast in Items)
                ClearToast((IAristeusToast)toast!);
        }

        private void ManagerOnToastQueued(object sender, AristeusToastQueuedEventArgs args)
        {
            if (MaxToasts <= 0) return;
            var toast = args.Toast;
            Items.Add(args.Toast);
            Manager.EnsureMaximum(MaxToasts);
            toast.AnimateShow();
        }

        private void ClearToast(IAristeusToast toast)
        {
            if (Manager.IsDismissed(toast)) return;
            toast.AnimateDismiss();
            Task.Delay(300).ContinueWith(_ =>
            {
                Items.Remove(toast);
                ToastPool.Return((AristeusToast)toast);
            }, TaskScheduler.FromCurrentSynchronizationContext());
        }

        static AristeusToastHost()
        {
            ManagerProperty.Changed.Subscribe(
                new Avalonia.Reactive.AnonymousObserver<AvaloniaPropertyChangedEventArgs<IAristeusToastManager>>(x =>
                    OnManagerPropertyChanged(x.Sender, x)));
        }
    }
}