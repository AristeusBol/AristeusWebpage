from torch.utils.data import Dataset
import cv2
import numpy as np
import torch
import pathlib

from utils.paths import resolve_root

class InferenceDataset(Dataset):
    def __init__(self, df, transform, root=None):
        if root is None:
            root = resolve_root(df['id'].iloc[0], candidates=("test", "."))
        self.root = pathlib.Path(root)

        self.df = df
        self.transform = transform
        self.paths = df['id'].values
        self.failed_paths = set()

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        path = self.root / self.paths[idx]
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            print(f"Warning: Could not load image {path}")
            self.failed_paths.add(str(path))
            img = np.zeros((1024, 1024, 3), dtype=np.uint8)

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        transformed = self.transform(image=img)
        img = transformed['image']

        return img, self.paths[idx]
