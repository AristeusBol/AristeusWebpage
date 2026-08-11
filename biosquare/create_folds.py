import pandas as pd
import numpy as np
import os
import pathlib
from iterstrat.ml_stratifiers import MultilabelStratifiedKFold

def create_folds(csv_path, output_dir, n_splits=5, seed=16999):
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} rows from {csv_path}")

    # Create quintiles for each target to use as multi-label stratification
    # This ensures each fold has similar distribution of Green, Dead and Clover
    for col in ["Dry_Green_g", "Dry_Dead_g", "Dry_Clover_g"]:
        label = col.replace("Dry_", "").replace("_g", "_q")
        df[label] = pd.qcut(df[col], q=5, labels=False, duplicates='drop')

    # Multi-label targets: each quintile column acts as a label dimension
    Y = df[["Green_q", "Dead_q", "Clover_q"]].values

    # Species grouping for metadata (not used in stratification)
    species_counts = df["Species"].value_counts()
    rare = species_counts[species_counts < n_splits].index
    df["strata"] = df["Species"].apply(lambda x: "Rare" if x in rare else x)

    # Dry_Total_g bin for metadata
    if "Dry_Total_g" in df.columns:
        df["target_bin"] = pd.qcut(df["Dry_Total_g"], q=10, labels=False, duplicates='drop')
    else:
         cols = [c for c in df.columns if 'Total' in c]
         if cols:
             df["target_bin"] = pd.qcut(df[cols[0]], q=10, labels=False, duplicates='drop')
         else:
             df["target_bin"] = 0

    mskf = MultilabelStratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    
    output_path = pathlib.Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    for fold, (train_idx, val_idx) in enumerate(mskf.split(df, Y)):
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
