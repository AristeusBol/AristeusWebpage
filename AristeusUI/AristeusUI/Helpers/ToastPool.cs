using System.Collections.Concurrent;
using AristeusUI.Controls;
using AristeusUI.Toasts;

namespace AristeusUI.Helpers;

internal static class ToastPool
{
    private static readonly ConcurrentBag<IAristeusToast> Pool = new();

    internal static IAristeusToast Get()
    {
        var toast = Pool.TryTake(out var item) ? item : new AristeusToast();
        return toast.ResetToDefault();
    }

    internal static void Return(IAristeusToast toast) => Pool.Add(toast);

    internal static void Return(IEnumerable<IAristeusToast> toasts)
    {
        foreach (var toast in toasts)
            Pool.Add(toast);
    }
}