import argparse
import os
import pathlib
import sys

import numpy as np
import torch

from config import Config
from trainer import Trainer
from utils.log_setup import setup_logging

torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
torch.backends.cudnn.benchmark = True
torch.set_float32_matmul_precision("high")


def set_seed(seed):
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)


def main(csv_files, save_path, log_path, config: Config):
    save_path.mkdir(parents=True, exist_ok=True)
    logger, listener = setup_logging(log_path)

    token = os.getenv("HF_TOKEN", None)
    try:
        trainer = Trainer(config, csv_files, save_path, log_path, token=token)
        trainer.fit()
    finally:
        listener.stop()


def parse_args():
    parser = argparse.ArgumentParser(description="Train biomass model across K folds")
    parser.add_argument("--folds_dir", type=pathlib.Path, default=None,
                        help="Directory containing fold_*.csv (default: data/folds/folds_<version>)")
    parser.add_argument("--version", type=str, default="v1", help="Experiment version (v1, v2, ...)")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch_size", type=int, default=2)
    parser.add_argument("--img_size", type=int, default=1024)
    parser.add_argument("--seed", type=int, default=16999)
    parser.add_argument("--only_fold", type=int, default=None, help="Train only this fold id (0-based)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    set_seed(args.seed)

    cfg = Config(
        epochs=args.epochs,
        batch_size=args.batch_size,
        img_size=(args.img_size, args.img_size),
        seed=args.seed,
        version=args.version,
    )
    if args.folds_dir is not None:
        cfg.folds_dir = args.folds_dir

    if not cfg.folds_dir.exists():
        print(f"Error: No se encontró el directorio de folds: {cfg.folds_dir}")
        sys.exit(1)

    fold_files = sorted(f for f in os.listdir(cfg.folds_dir) if f.startswith("fold_") and f.endswith(".csv"))
    if not fold_files:
        print(f"Error: No se encontraron fold_*.csv en {cfg.folds_dir}")
        sys.exit(1)
    if args.only_fold is not None:
        fold_files = [f"fold_{args.only_fold}.csv"] if f"fold_{args.only_fold}.csv" in fold_files else []
        if not fold_files:
            print(f"Error: fold_{args.only_fold}.csv no existe en {cfg.folds_dir}")
            sys.exit(1)

    for fold_file in fold_files:
        fold_id = fold_file[len("fold_"):-len(".csv")]
        df_path = cfg.folds_dir / fold_file
        save_path = cfg.fold_checkpoints_dir(fold_id)
        log_path = cfg.fold_logs_dir(fold_id)
        try:
            main(df_path, save_path, log_path, cfg)
        except KeyboardInterrupt:
            print("[!] Interrumpido por el usuario.")
            sys.exit(0)
        except Exception as exc:
            print(f"[!] Fold {fold_file} falló: {exc}")
            continue
