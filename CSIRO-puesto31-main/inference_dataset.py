from torch.utils.data import Dataset
import cv2
import numpy as np
import os
import torch
import pathlib

class InferenceDataset(Dataset):
    def __init__(self, df, transform, root=None):
        if root is not None:
            self.root = pathlib.Path(root)
        else:
            sample_path = df['id'].iloc[0]
            if pathlib.Path(sample_path).exists():
                self.root = pathlib.Path(".")
            elif (pathlib.Path("..") / sample_path).exists():
                self.root = pathlib.Path("..")
            else:
                self.root = pathlib.Path("..")

        self.df = df
        self.transform = transform
        self.paths = df['id'].values

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        path = self.root / self.paths[idx]
        
        if not os.path.exists(path):
             if os.path.exists(self.paths[idx]):
                 path = self.paths[idx]
             else:
                 path = pathlib.Path("./datasets") / self.paths[idx]

        img = cv2.imread(str(path), -1)
        if img is None:
            print(f"Warning: Could not load image {path}")
            img = np.zeros((512, 1024, 3), dtype=np.uint8)
            
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        h, w, c = img.shape
        half_w = w // 2

        transformed = self.transform(image=img[:, :half_w], image_1=img[:, half_w:])
        new0 = transformed['image']
        new1 = transformed['image_1']
        
        return new0, new1, self.paths[idx]
