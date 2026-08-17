import numpy as np
import torch

from dataset import DEFAULT_SCALES

R2_WEIGHTS = np.array([0.5, 0.25, 0.25])

MAE_BINS = [0, 5, 15, 30, float('inf')]
MAE_BIN_LABELS = ["0g", "0_5g", "5_15g", "15_30g", "30+"]
TARGET_NAMES = ["Green", "Dead", "Total"]


def postprocess(data, is_gt=False, scales=None):
    # data: (N, 2) -> [Dry_Green_g, Dry_Dead_g]
    if scales is None:
        scales = DEFAULT_SCALES
    scales = scales.detach().cpu().numpy() if torch.is_tensor(scales) else np.asarray(scales)
    data = data * scales[None]
    if not is_gt:
        data[data < 0.1] = 0.0
    # Derive Total = Green + Dead -> (N, 3): [Green, Dead, Total]
    total = data[:, 0] + data[:, 1]
    data = np.concatenate([data, total[:, None]], axis=1)
    return data


def get_balance_metric(scores, lambda_penalty=0.1):
    mean_score = np.mean(scores)
    std_dev = np.std(scores)
    return mean_score - (lambda_penalty * std_dev)


def weighted_r2_score(y_true: np.ndarray, y_pred: np.ndarray):
    weights = R2_WEIGHTS
    r2_scores = []
    for i in range(y_true.shape[1]):
        yt = y_true[:, i]; yp = y_pred[:, i]
        ss_res = np.sum((yt - yp) ** 2)
        ss_tot = np.sum((yt - np.mean(yt)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        r2_scores.append(r2)
    r2_scores = np.array(r2_scores)
    weighted = np.sum(r2_scores * weights) / np.sum(weights)
    return weighted, r2_scores


def weighted_r2_score_global(y_true: np.ndarray, y_pred: np.ndarray):
    weights = R2_WEIGHTS
    flat_true = y_true.copy().reshape(-1)
    flat_pred = y_pred.copy().reshape(-1)
    w = np.tile(weights, y_true.shape[0])
    mean_w = np.sum(w * flat_true) / np.sum(w)
    ss_res = np.sum(w * (flat_true - flat_pred) ** 2)
    ss_tot = np.sum(w * (flat_true - mean_w) ** 2)
    global_r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    avg_r2, per_r2 = weighted_r2_score(y_true, y_pred)
    return global_r2, avg_r2, per_r2


def compute_regression_metrics(y_true, y_pred):
    mae = np.mean(np.abs(y_pred - y_true), axis=0)
    rmse = np.sqrt(np.mean((y_pred - y_true) ** 2, axis=0))
    rmsle = np.sqrt(np.mean((np.log1p(y_pred) - np.log1p(y_true)) ** 2, axis=0))

    mae_bucket = {}
    for i, name in enumerate(TARGET_NAMES):
        mask_zero = y_true[:, i] == 0
        mae_bucket[f"{name}_{MAE_BIN_LABELS[0]}"] = (
            float(np.mean(np.abs(y_pred[mask_zero, i] - y_true[mask_zero, i]))) if mask_zero.sum() > 0 else 0.0
        )
        for j in range(1, len(MAE_BINS)):
            lo, hi = MAE_BINS[j-1], MAE_BINS[j]
            mask = (y_true[:, i] > lo) & (y_true[:, i] <= hi)
            if mask.sum() > 0:
                mae_bucket[f"{name}_{MAE_BIN_LABELS[j]}"] = float(np.mean(np.abs(y_pred[mask, i] - y_true[mask, i])))
            else:
                mae_bucket[f"{name}_{MAE_BIN_LABELS[j]}"] = 0.0

    return (
        [float(round(i, 5)) for i in mae],
        [float(round(i, 5)) for i in rmse],
        [float(round(i, 5)) for i in rmsle],
        mae_bucket,
    )
