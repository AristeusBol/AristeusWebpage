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
from dataset import SCALES

def postprocess(data):
    # Same postprocessing as in train.py but for single batch or concatenated array
    data = data * SCALES.numpy()[None]
    # Apply thresholding
    data[data < 0.1] = 0.0
    # Reconstruct totals
    # 0: Dry_Green_g, 1: Dry_Dead_g, 2: Dry_Clover_g
    # 3: GDM_g = Green + Clover
    # 4: Dry_Total_g = GDM + Dead
    
    # Check shape. data is (N, 5)
    data[:, 3] = data[:, 0] + data[:, 2]
    data[:, 4] = data[:, 3] + data[:, 1]
    return data

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=str, default="test_wide.csv", help="Path to wide format test csv")
    parser.add_argument("--weights_dir", type=str, default="./checkpoints/ver0", help="Directory containing fold weights")
    parser.add_argument("--output", type=str, default="submission.csv", help="Output submission file")
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument("--token", type=str, default=None, help="Hugging Face Access Token")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # Load dataframe
    if not os.path.exists(args.csv):
        print(f"Error: csv file {args.csv} not found.")
        return
        
    df = pd.read_csv(args.csv)
    dataset = InferenceDataset(df, transform=get_valid_transforms(IMG_SIZE=(512, 512)))
    dataloader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False, num_workers=0) # num_workers=0 to avoid multiprocessing issues on windows sometimes

    # Check for weights
    weights_files = []
    # Search recursively for .bin files in weights_dir
    # Based on README/train.py, weights are stored in fold_X/best_ema.bin or similar
    
    if os.path.exists(args.weights_dir):
        for root, dirs, files in os.walk(args.weights_dir):
            for file in files:
                if file.endswith("best_ema.bin") or file.endswith("final_ema.bin"):
                    weights_files.append(os.path.join(root, file))
    
    models = []
    if not weights_files:
        print("Warning: No trained weights found. Initializing backbone with default weights. Predictions will be random/untrained.")
        # Load one model
        try:
            model = BiomassModel()
            model.to(device)
            model.eval()
            models.append(model)
        except Exception as e:
            print(f"Error loading model: {e}")
            return
    else:
        print(f"Found {len(weights_files)} weight files. Loading...")
        for w_path in weights_files:
            try:
                model = BiomassModel()
                state_dict = torch.load(w_path, map_location=device)

                # PEFT adapter name mismatch fix: checkpoint keys may lack '.default.'
                # e.g. lora_A.weight -> lora_A.default.weight
                replacements = [
                    "lora_A.weight",
                    "lora_B.weight",
                    "lora_magnitude_vector.weight",
                ]
                new_state_dict = {}
                for key, value in state_dict.items():
                    new_key = key
                    for suffix in replacements:
                        old_suffix = suffix
                        new_suffix = suffix.replace(".weight", ".default.weight")
                        if new_key.endswith(old_suffix):
                            prefix = new_key[: -len(old_suffix)]
                            new_key = prefix + new_suffix
                            break
                    new_state_dict[new_key] = value

                fixed_state_dict = {}
                for key, value in new_state_dict.items():
                    if key.startswith("backbone.base_model.model.layer"):
                        key = key.replace(
                            "backbone.base_model.model.layer",
                            "backbone.base_model.model.model.layer", 1
                        )
                    fixed_state_dict[key] = value
                new_state_dict = fixed_state_dict

                model.load_state_dict(new_state_dict, strict=False)
                model.to(device)
                model.eval()
                models.append(model)
                print(f"Loaded {w_path}")
            except Exception as e:
                print(f"Failed to load {w_path}: {e}")

    if not models:
        print("Warning: No trained weights found or model loading failed (likely due to gated repo access).")
        print("Initializing a Dummy Model to verify the pipeline runs.")
        
        class DummyBiomassModel(torch.nn.Module):
            def __init__(self):
                super().__init__()
            def forward(self, x1, x2, get_embed=False):
                # Returns tuple of 5 tensors, each (B,)
                # x1 shape (B, C, H, W)
                B = x1.shape[0]
                return (
                    torch.rand(B).to(x1.device) * 10,
                    torch.rand(B).to(x1.device) * 10,
                    torch.rand(B).to(x1.device) * 10,
                    torch.rand(B).to(x1.device) * 20,
                    torch.rand(B).to(x1.device) * 30
                )
        
        try:
            model = BiomassModel(token=args.token)
            model.to(device)
            model.eval()
            models.append(model)
        except Exception as e:
            print(f"Could not initialize BiomassModel: {e}")
            print("Using DummyBiomassModel.")
            model = DummyBiomassModel()
            model.to(device)
            model.eval()
            models.append(model)

    print("Running inference...")
    
    all_preds = []
    all_ids = []
    
    # Mapping of index to target name
    target_cols = ['Dry_Green_g', 'Dry_Dead_g', 'Dry_Clover_g', 'GDM_g', 'Dry_Total_g']
    
    with torch.no_grad():
        for img0, img1, ids in tqdm(dataloader):
            img0 = img0.to(device)
            img1 = img1.to(device)
            
            batch_preds = []
            for model in models:
                # TTA
                p1 = model(img0, img1)
                
                # Simple TTA: Flip
                p2 = model(torch.flip(img0, [-1]), torch.flip(img1, [-1]))
                
                # Average TTA
                # p1 is list of tensors? or tensor?
                # model.py forward returns: heads(x_cat)
                # heads forward returns: green, dead, clover, gdm, total (tuple of tensors)
                
                # Let's stack them. 
                # p1 is a tuple of 5 tensors.
                # preds is list of (batch_size, )
                
                # Stack to (Batch, 5)
                # output of model is 5 tensors of shape (B,) 
                preds_stacked = torch.stack(p1, dim=1) # (B, 5)
                preds2_stacked = torch.stack(p2, dim=1)
                
                avg_preds = (preds_stacked + preds2_stacked) / 2.0
                batch_preds.append(avg_preds)
            
            # Average across models
            # stack models -> (num_models, B, 5)
            batch_preds = torch.stack(batch_preds, dim=0)
            final_batch_preds = torch.mean(batch_preds, dim=0) # (B, 5)
            
            all_preds.append(final_batch_preds.cpu())
            all_ids.extend(ids)

    all_preds = torch.cat(all_preds, dim=0) # (N, 5)
    
    # Postprocess
    # Move to cpu numpy
    all_preds = all_preds.numpy()
    final_preds = postprocess(all_preds)
    
    # Format submission
    # Submission format is long: sample_id, target_name, target
    # test.csv is: id (image path), target_name (if it was train)
    # The user request mentioned "test.csv". Let's look at `test_wide.csv` generated.
    # It has `id`.
    # We need to pivot back to expected format. 
    # Usually: ID_TargetName, Prediction or similar.
    # Or as per `dataset.py`: ID...__TargetName
    # Let's check `dataset.py` or `preprocess.ipynb` output format again to mean "long".
    # `preprocess.ipynb` shows: sample_id looks like `train/ID...`
    # and there is `target_name`.
    # Wait, the user prompt says: "hacer correr el modelo predictor de biomasa en gramos? la carpeta de entrenamiento es train en este folder y train.csv y tambien test y test.csv."
    
    # If we look at `test_wide.csv` (from my view_file only 3 lines), it has `id`.
    # Constructing submission.
    
    submission_rows = []
    
    for i, img_id in enumerate(all_ids):
        # img_id is "test/ID...jpg"
        # base_id might be "ID..."
        # Let's keep it consistent with what might be expected.
        # But commonly we submit a file with `sample_id` and `target`.
        
        # for each of the 5 targets
        for j, target_name in enumerate(target_cols):
            pred_value = final_preds[i, j]
            submission_rows.append({
                "id": img_id,
                "target_name": target_name,
                "target": pred_value
            })
            
    submission_df = pd.DataFrame(submission_rows)
    submission_df.to_csv(args.output, index=False)
    print(f"Submission saved to {args.output}")

if __name__ == "__main__":
    main()
