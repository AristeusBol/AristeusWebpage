import numpy as np
import cv2 
from torch.utils.data import Dataset
import torch
import pathlib 

from utils.paths import resolve_root

ALL_TARGET_COLS = ['Dry_Green_g','Dry_Dead_g']
DEFAULT_SCALES = torch.tensor([360.0, 275.0]).float()

def compute_scales(df, margin=0.1):
    maxima = df[ALL_TARGET_COLS].max(axis=0).astype(float).values
    scales = np.maximum(maxima * (1.0 + margin), 1.0)
    return torch.tensor(scales, dtype=torch.float32)

class BiomassDataset(Dataset):
    def __init__(self, df, transform, root=None, scales=None):
        if root is None:
            root = resolve_root(df['id'].iloc[0], candidates=("train", "."))
        self.root = pathlib.Path(root)

        self.df = df
        self.transform = transform
        self.paths = df['id'].values
        if scales is None:
            scales = compute_scales(df)
        self.scales = scales
        self.labels = torch.from_numpy(df[ALL_TARGET_COLS].values.copy()).float()
        bad_labels = ~np.isfinite(self.labels.numpy())
        if bad_labels.any():
            print(f"WARNING: {bad_labels.sum()} valores no finitos en labels (NaN/inf)")
        self.labels /= scales.unsqueeze(0)

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        path = self.root / self.paths[idx]
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            img = cv2.imread(self.paths[idx], cv2.IMREAD_COLOR)

        if img is None:
            raise FileNotFoundError(f"Could not load image: {path} or {self.paths[idx]}")

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        transformed = self.transform(image=img)
        img = transformed['image']
        label = self.labels[idx]
        return img, label
