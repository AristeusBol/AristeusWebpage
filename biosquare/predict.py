import torch
import pandas as pd
import pathlib
import os
import argparse
from torch.utils.data import DataLoader
from tqdm import tqdm
import numpy as np
from inference_dataset import InferenceDataset
from transforms import get_valid_transforms
from model import BiomassModel
from metrics import postprocess
from config import Config

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=str, required=True, help="Path to csv with an 'id' column (one row per image)")
    parser.add_argument("--images_dir", type=str, required=True, help="Directory containing the images")
    parser.add_argument("--weights_dir", type=str, default=None, help="Directory containing fold weights")
    parser.add_argument("--output", type=str, default="predictions.csv", help="Output file")
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument("--img_size", type=int, default=1024)
    parser.add_argument("--token", type=str, default=None, help="Hugging Face Access Token")
    args = parser.parse_args()

    cfg = Config(img_size=(args.img_size, args.img_size))
    weights_dir = args.weights_dir or cfg.checkpoints_dir / cfg.version

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    if not os.path.exists(args.csv):
        print(f"Error: csv file {args.csv} not found.")
        return

    df = pd.read_csv(args.csv)
    if "id" not in df.columns:
        print(f"Error: csv file {args.csv} must contain an 'id' column.")
        return

    dataset = InferenceDataset(df, transform=get_valid_transforms(IMG_SIZE=cfg.img_size), root=args.images_dir)
    dataloader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False, num_workers=0)

    weights_files = []
    if os.path.exists(weights_dir):
        for root, dirs, files in os.walk(weights_dir):
            if "best_ema.pt" in files:
                weights_files.append(os.path.join(root, "best_ema.pt"))

    models = []
    if not weights_files:
        print(f"Error: No 'best_ema.pt' weights found in {weights_dir}. Aborting.")
        return
    print(f"Found {len(weights_files)} weight files. Loading...")
    for w_path in weights_files:
        try:
            model = BiomassModel(img_size=args.img_size, token=args.token)
            state_dict = torch.load(w_path, map_location=device)
            model.load_state_dict(state_dict, strict=True)
            model.to(device)
            model.eval()
            models.append(model)
            print(f"Loaded {w_path}")
        except Exception as e:
            print(f"Failed to load {w_path}: {e}")

    if not models:
        print("Error: No model could be loaded. Aborting.")
        return

    print("Running inference...")

    if dataset.failed_paths:
        failed = list(dataset.failed_paths)
        print(f"Warning: {len(failed)} image(s) could not be loaded: {failed[:5]}{'...' if len(failed) > 5 else ''}")

    all_preds = []
    all_ids = []
    w1, w2, w3, w4 = cfg.tta_weights

    autocast_enabled = device.type == "cuda"
    with torch.no_grad(), torch.autocast(device.type, dtype=torch.float16, enabled=autocast_enabled):
        for img, ids in tqdm(dataloader):
            img = img.to(device)

            batch_preds = []
            for model in models:
                p1 = model(img)
                p2 = model(torch.flip(img, [-1]))
                p3 = model(torch.flip(img, [-2]))
                p4 = model(torch.flip(img, [-2, -1]))

                preds_stacked = torch.stack(p1, dim=1)
                preds2_stacked = torch.stack(p2, dim=1)
                preds3_stacked = torch.stack(p3, dim=1)
                preds4_stacked = torch.stack(p4, dim=1)

                avg_preds = (preds_stacked * w1 + preds2_stacked * w2
                             + preds3_stacked * w3 + preds4_stacked * w4)
                batch_preds.append(avg_preds)

            batch_preds = torch.stack(batch_preds, dim=0)
            final_batch_preds = torch.mean(batch_preds, dim=0).float()

            all_preds.append(final_batch_preds.cpu())
            all_ids.extend(ids)

    all_preds = torch.cat(all_preds, dim=0).numpy()
    scales = models[0].scales.detach().cpu()
    final_preds = postprocess(all_preds, scales=scales)

    target_cols = ['Dry_Green_g', 'Dry_Dead_g', 'Dry_Total_g']
    submission_df = pd.DataFrame(final_preds, columns=target_cols)
    submission_df.insert(0, "id", all_ids)
    submission_df.to_csv(args.output, index=False)
    print(f"Predictions saved to {args.output}")

if __name__ == "__main__":
    main()
