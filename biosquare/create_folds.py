import pandas as pd
import os
import pathlib
from sklearn.model_selection import KFold

TARGET_MAP = {
    "Dry_Green_g": "materia verde seca por m2",
    "Dry_Dead_g": "materia muerta seca por m2",
}

def read_csv_any_encoding(path):
    for enc in ["utf-8", "latin-1"]:
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not read {path} with utf-8 or latin-1")

def create_folds(csv_path, output_dir, n_splits=5, seed=16999):
    df = read_csv_any_encoding(csv_path)
    print(f"Loaded {len(df)} rows from {csv_path}")

    fold_df = df.copy()
    fold_df["id"] = fold_df["Id"]
    for target, src in TARGET_MAP.items():
        if src not in fold_df.columns:
            raise KeyError(f"Column '{src}' not found in {csv_path}")
        fold_df[target] = fold_df[src]

    kf = KFold(n_splits=n_splits, shuffle=True, random_state=seed)

    output_path = pathlib.Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    for fold, (train_idx, val_idx) in enumerate(kf.split(fold_df)):
        out = fold_df.copy()
        out["split"] = "train"
        out.loc[val_idx, "split"] = "val"
        out_name = output_path / f"fold_{fold}.csv"
        keep = ["id"] + list(TARGET_MAP.keys()) + ["split"]
        out[keep].to_csv(out_name, index=False)
        print(f"Created {out_name} (Train: {len(train_idx)}, Val: {len(val_idx)})")

if __name__ == "__main__":
    train_gg_path = "data/raw/train_wide.csv"
    if not os.path.exists(train_gg_path):
        if os.path.exists("../data/raw/train_wide.csv"):
            train_gg_path = "../data/raw/train_wide.csv"
        else:
            print("Error: data/raw/train_wide.csv not found.")
            exit(1)

    create_folds(train_gg_path, "./data/folds/folds_v1")
