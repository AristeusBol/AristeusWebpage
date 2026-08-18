using Avalonia.Controls.Notifications;

namespace AristeusUI.Dialogs
{
    public static class FluentAristeusDialogBuilder
    {
        #region Content

        /// <summary>
        /// Creates a <see cref="AristeusDialogBuilder"/> instance that can be used to construct a <see cref="IAristeusDialog"/>
        /// </summary>
        public static AristeusDialogBuilder CreateDialog(this IAristeusDialogManager mgr) => new(mgr);

        /// <summary>
        /// Gives the dialog a "type" which will display an icon representing it.
        /// This can be used for MessageBox style dialogs.
        /// </summary>
        public static AristeusDialogBuilder OfType(this AristeusDialogBuilder builder, NotificationType type)
        {
            builder.SetType(type);
            return builder;
        }

        /// <summary>
        /// Gives the dialog a title.
        /// </summary>
        public static AristeusDialogBuilder WithTitle(this AristeusDialogBuilder builder, string title)
        {
            builder.SetTitle(title);
            return builder;
        }

        /// <summary>
        /// Gives the dialog content. This content can be a ViewModel if desired.
        /// </summary>
        public static AristeusDialogBuilder WithContent(this AristeusDialogBuilder builder, object content)
        {
            builder.SetContent(content);
            return builder;
        }

        /// <summary>
        /// Hide Card background.
        /// </summary>
        public static AristeusDialogBuilder ShowCardBackground(this AristeusDialogBuilder builder, bool show)
        {
            builder.SetShowCardBackground(show);
            return builder;
        }

        /// <summary>
        /// Gives the dialog a ViewModel. If this is used, Title/Content are ignored and only the ViewModel is rendered - the View being located by the usual strategy.
        /// This is useful for custom dialogs.
        /// </summary>
        public static AristeusDialogBuilder WithViewModel(this AristeusDialogBuilder builder, Func<IAristeusDialog, object> viewModel, bool isViewModelOnly = true)
        {
            builder.SetViewModel(viewModel, isViewModelOnly);
            return builder;
        }

        #endregion Content

        #region Dismissing

        /// <summary>
        /// Begins a dismiss chain.
        /// </summary>
        public static AristeusDialogBuilder.DismissDialog Dismiss(this AristeusDialogBuilder builder) => new(builder);

        /// <summary>
        /// Allows the dialog to be dismissed simply by clicking the background
        /// </summary>
        public static AristeusDialogBuilder ByClickingBackground(this AristeusDialogBuilder.DismissDialog dismissBuilder)
        {
            dismissBuilder.Builder.SetCanDismissWithBackgroundClick(true);
            return dismissBuilder.Builder;
        }

        #endregion Dismissing

        #region Actions

        /// <summary>
        /// Adds a button to the bottom of the dialog which will call the supplied callback when clicked.
        /// Any number of buttons can be added to the dialog.
        /// </summary>
        public static AristeusDialogBuilder WithActionButton(this AristeusDialogBuilder builder, object? content, Action<IAristeusDialog> onClicked,
            bool dismissOnClick = false, params string[] classes)
        {
            builder.AddActionButton(content, onClicked, dismissOnClick, classes);
            return builder;
        }

        /// <summary>
        /// Provides a callback that will be called when this dialog is dismissed for any reason.
        /// </summary>
        public static AristeusDialogBuilder OnDismissed(this AristeusDialogBuilder builder, Action<IAristeusDialog> onDismissed)
        {
            builder.SetOnDismissed(onDismissed);
            return builder;
        }

        /// <summary>
        /// Adds Support for 'await'ing the dialog to being closed via <see cref="AristeusDialogBuilder.TryShowAsync(CancellationToken)"/>
        /// <para>
        /// Adds a 'Yes' and 'No' button that both will close/dismiss the dialog and also allows for waiting of either of the buttons being pressed.
        /// </para>
        /// <para>
        /// Pressing the 'Yes' button will result in a 'true' result, while pressing the 'No' button will result in a 'false' result.
        /// </para>
        /// </summary>
        public static AristeusDialogBuilder WithYesNoResult(this AristeusDialogBuilder builder, object? yesButtonContent, object? noButtonContent, params string[] classes)
        {
            builder.Completion = new TaskCompletionSource<bool>();

            builder.AddActionButton(yesButtonContent, dialog => builder.Completion.SetResult(true), true, classes);
            builder.AddActionButton(noButtonContent, dialog => builder.Completion.SetResult(false), true, classes);

            return builder;
        }

        /// <summary>
        /// Adds Support for 'await'ing the dialog to being closed via <see cref="AristeusDialogBuilder.TryShowAsync(CancellationToken)"/>
        /// <para>
        /// Adds a 'Ok' button that will close/dismiss the dialog and also allows for waiting of the button being pressed.
        /// </para>
        /// <para>
        /// Pressing the 'Ok' button will result in a 'true' result.
        /// </para>
        /// </summary>
        public static AristeusDialogBuilder WithOkResult(this AristeusDialogBuilder builder, object? okButtonContent, params string[] classes)
        {
            builder.Completion = new TaskCompletionSource<bool>();

            builder.AddActionButton(okButtonContent, dialog => builder.Completion.SetResult(true), true, classes);

            return builder;
        }

        #endregion Actions
    }
}