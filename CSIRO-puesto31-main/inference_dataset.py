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

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        # Image paths in df are like "test/ID123.jpg" or "train/ID123.jpg"
        # The root should be where these folders are located.
        # Based on prepare_data.py finding csvs in `..`, the images should also be relative to that.
        
        path = self.root / self.paths[idx]
        
        # Check if file exists, if not try absolute path or relative to current dir
        if not os.path.exists(path):
             # Try checking in current directory if root is not correct
             if os.path.exists(self.paths[idx]):
                 path = self.paths[idx]
             else:
                 # Last resort, maybe datasets folder
                 path = pathlib.Path("./datasets") / self.paths[idx]

        img = cv2.imread(str(path), -1)
        if img is None:
            # Return dummy if image load fails to avoid crashing
            print(f"Warning: Could not load image {path}")
            img = np.zeros((512, 1024, 3), dtype=np.uint8)
            
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Split image into left and right 
        # Original image is 2:1 aspect ratio, e.g. 1024x512? or 2048x1024?
        # dataset.py uses img[:, :1000] and img[:, 1000:] but hardcoded 1000 might be risky if image size varies.
        # However, let's stick to the logic in dataset.py or make it robust.
        # The README says 2:1 aspect ratio.
        
        h, w, c = img.shape
        half_w = w // 2
        
        # We will use the same transform logic as dataset.py but with dynamic width
        new0 = self.transform(image=img[:, :half_w])['image']
        new1 = self.transform(image=img[:, half_w:])['image']
        
        return new0, new1, self.paths[idx]
