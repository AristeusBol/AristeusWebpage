import numpy as np
import cv2 
from torch.utils.data import Dataset
import torch
import pathlib 

ALL_TARGET_COLS = ['Dry_Green_g','Dry_Dead_g','Dry_Clover_g','GDM_g','Dry_Total_g']
SCALES = torch.tensor([157.9836, 83.8407, 71.7865, 157.9836, 185.7000]).float()

class BiomassDataset(Dataset):
    def __init__(self, df, transform, root=None):
        if root is not None:
            self.root = pathlib.Path(root)
        else:
            # Robust detection: check if images are in current dir or parent dir
            # based on the first image path in the dataframe
            sample_path = df['id'].iloc[0]
            if pathlib.Path(sample_path).exists():
                self.root = pathlib.Path(".")
            elif (pathlib.Path("..") / sample_path).exists():
                self.root = pathlib.Path("..")
            else:
                # Fallback to default parent if nothing found
                self.root = pathlib.Path("..")
                
        self.df = df
        self.transform = transform
        self.paths = df['id'].values
        self.labels = torch.from_numpy(df[ALL_TARGET_COLS].values).float()
        self.labels /= SCALES.unsqueeze(0)

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        path = self.root / self.paths[idx]
        img = cv2.imread(str(path), -1)
        if img is None:
            # Fallback if image not found in parent, try current
            img = cv2.imread(self.paths[idx], -1)
            
        if img is None:
            raise FileNotFoundError(f"Could not load image: {path} or {self.paths[idx]}")

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, c = img.shape
        half_w = w // 2
        new0 = self.transform(image=img[:, :half_w])['image']
        new1 = self.transform(image=img[:, half_w:])['image']
        label = self.labels[idx] 
        return new0, new1, label