using System.Collections.Concurrent;
using System.Collections.Generic;
using AristeusUI.Controls;
using AristeusUI.Dialogs;

namespace AristeusUI.Helpers
{
    internal static class DialogPool
    {
        private static readonly ConcurrentStack<IAristeusDialog> Pool = new();

        static DialogPool()
        {
            Pool.Push(new AristeusDialog());
            Pool.Push(new AristeusDialog());
        }
        
        internal static IAristeusDialog Get()
        {
            var dialog = Pool.TryPop(out var item) ? item : new AristeusDialog();
            dialog.ResetToDefault();
            return dialog;
        }

        internal static void Return(IAristeusDialog dialog) => Pool.Push(dialog);

        internal static void Return(IEnumerable<IAristeusDialog> dialogs)
        {
            foreach (var dialog in dialogs)
            {
                Pool.Push(dialog);
            }
        }
    }
}