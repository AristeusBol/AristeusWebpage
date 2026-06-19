import pandas as pd
import numpy as np
import os
import pathlib
from sklearn.model_selection import StratifiedGroupKFold

def create_folds(csv_path, output_dir, n_splits=5, seed=16999):
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} rows from {csv_path}")

    # Following logic from preprocess.ipynb
    # Targets: Dry_Green_g, Dry_Dead_g, Dry_Clover_g, GDM_g, Dry_Total_g
    # We need a categorization for stratification
    
    # Create bins for Dry_Total_g
    if "Dry_Total_g" in df.columns:
        df["target_bin"] = pd.qcut(df["Dry_Total_g"], q=10, labels=False, duplicates='drop')
    else:
        # Fallback if names are different
         cols = [c for c in df.columns if 'Total' in c]
         if cols:
             df["target_bin"] = pd.qcut(df[cols[0]], q=10, labels=False, duplicates='drop')
         else:
             df["target_bin"] = 0

    # Stratification strata: Species + State + target_bin
    df["strata"] = (
        df["Species"].astype(str) + "_" + 
        df["State"].astype(str) + "_" + 
        df["target_bin"].astype(str)
    )

    # Groups: Sampling_Date (to avoid leakage within same date/location)
    groups = df["Sampling_Date"].values
    
    sgkf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    
    output_path = pathlib.Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    for fold, (train_idx, val_idx) in enumerate(sgkf.split(df, df["strata"], groups=groups)):
        fold_df = df.copy()
        # mark split
        fold_df["split"] = "train"
        fold_df.loc[val_idx, "split"] = "val"
        
        # In train.py it expects "split" column to distinguish
        out_name = output_path / f"fold_{fold}.csv"
        fold_df.to_csv(out_name, index=False)
        print(f"Created {out_name} (Train: {len(train_idx)}, Val: {len(val_idx)})")

if __name__ == "__main__":
    # Use the train_wide.csv generated earlier
    train_wide_path = "train_wide.csv"
    if not os.path.exists(train_wide_path):
        # search in current or parent
        if os.path.exists("../train_wide.csv"):
            train_wide_path = "../train_wide.csv"
        else:
            print("Error: train_wide.csv not found. Run prepare_data.py first.")
            exit(1)
            
    create_folds(train_wide_path, "./datasets/fold_news1")
