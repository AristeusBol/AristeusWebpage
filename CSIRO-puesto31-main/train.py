import os, numpy as np, pandas as pd, csv, logging
import tqdm
import pathlib
from utils.log_setup import setup_logging

import torch, torch.optim as optim
from torch.utils.data import DataLoader
from timm.utils import ModelEmaV2
from torch.optim.lr_scheduler import LinearLR, ReduceLROnPlateau
from dataset import BiomassDataset, SCALES
from transforms import get_train_transforms, get_valid_transforms
from model import BiomassModel, save_checkpoint
from loss import BiomassLoss
from metrics import weighted_r2_score_global
from peft import PeftModel

torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
torch.backends.cudnn.benchmark = True
torch.set_float32_matmul_precision("high")



def load_dataloader(csv_files, ds_type="biomass"):
    df = pd.read_csv(csv_files)
    train_df = df[df["split"] == "train"]
    val_df = df[df["split"] != "train"]
    train_ds = BiomassDataset(train_df, transform=get_train_transforms(IMG_SIZE=(512, 512)))
    val_ds = BiomassDataset(val_df, transform=get_valid_transforms(IMG_SIZE=(512, 512)))
    # Set num_workers=0 for Windows stability
    train_loader = DataLoader(train_ds, batch_size=4, shuffle=True, num_workers=0, pin_memory=True, drop_last=True)
    val_loader = DataLoader(val_ds, batch_size=4, shuffle=False, num_workers=0, pin_memory=True, drop_last=False)
    return train_loader, val_loader

def build_optimizer(model: BiomassModel):
    return optim.AdamW([
        {
            'params': model.backbone.parameters(), 
            'lr': 1e-4,
            'weight_decay': 1e-3
        },
        {
            'params': model.heads.parameters(),     
            'lr': 1e-3,
            'weight_decay': 1e-3
        },
])

def postprocess(data, is_gt=False):
    data = data * SCALES.numpy()[None]
    if is_gt==False:
        data[data < 0.1] = 0.0
        data[:, 3] = data[:, 0] + data[:, 2]
        data[:, 4] = data[:, 3] + data[:, 1]
    return data

def get_balance_metric(scores, lambda_penalty=0.1):
    mean_score = np.mean(scores)
    std_dev = np.std(scores)
    combined_metric = mean_score - (lambda_penalty * std_dev)
    return combined_metric
    
def _train(model, train_loader, criterion, optimizer, scheduler, ema, device, epoch, WARMUP):
    model.train()
    logger = logging.getLogger("biomass")
    all_loss = []
    for idx, b in (pbar := tqdm.tqdm(enumerate(train_loader), total=len(train_loader))):
        logger.debug("Batch %d started", idx)
        img0, img1, labels = b
        logger.debug("Batch %d | Shapes: %s %s", idx, img0.shape, labels.shape)
        img0 = img0.to(device)
        img1 = img1.to(device)
        labels = labels.to(device)
        logger.debug("Batch %d moved to device", idx)
        with torch.autocast(
            device.type if device.type != 'cpu' else 'cpu', 
            dtype=torch.bfloat16 if device.type != 'cpu' else torch.float32, 
            enabled=device.type != 'cpu'
        ):
            logger.debug("Batch %d forward pass starting", idx)
            preds = model(img0, img1)
        
        logger.debug("Batch %d forward done. Calculating loss.", idx)
        loss, loss_full = criterion(preds, labels)
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        ema.update(model)
        pbar.set_postfix({'loss': loss.item()})
        all_loss.append([j.detach().cpu().item() for j in loss_full])
        if epoch < WARMUP:
            scheduler.step()
        logger.debug("Batch %d completed", idx)
    all_loss = np.array(all_loss)
    all_loss = all_loss.mean(0)
    all_loss = [float(round(i, 5)) for i in all_loss]
    return all_loss 

def _eval(eval_model, val_loader, device, use_tta=False):
    all_pred = []
    all_labels = []
    eval_model.eval()
    for idx, b in tqdm.tqdm(enumerate(val_loader), total=len(val_loader), leave=False):
        img0, img1, labels = b
        img0 = img0.to(device, dtype=torch.float32)
        img1 = img1.to(device, dtype=torch.float32)
        with torch.no_grad():
            preds = eval_model(img0, img1)
            if use_tta:
                preds1 = eval_model(torch.flip(img1, [-1]), torch.flip(img0, [-1]))
                preds2 = eval_model(torch.flip(img1, [-2]), torch.flip(img0, [-2]))
                preds3 = eval_model(torch.flip(img1, [-2,-1]), torch.flip(img0, [-2,-1]))
                preds = [
                    (preds[j]*0.4 + preds1[j]*0.2 + preds2[j]*0.2 + preds3[j]*0.2) for j in range(len(preds))
                ]
        preds = torch.stack(preds, -1).cpu().numpy()
        all_pred.append(preds)
        all_labels.append(labels.numpy())

    all_pred = np.concatenate(all_pred, 0)
    all_pred = postprocess(all_pred.squeeze(), is_gt=False)
    all_labels = np.concatenate(all_labels, 0)
    all_labels = postprocess(all_labels.squeeze(), is_gt=True)
    
    mae = np.mean(np.abs(all_pred - all_labels), axis=0)
    global_score, score, score_per = weighted_r2_score_global(all_labels, all_pred)
    balanced_score = get_balance_metric(score_per[:3])
    
    mae = [float(round(i, 5)) for i in mae]
    score_per = [round(float(s), 4) for s in score_per]
    return mae, global_score, score, score_per, balanced_score

def main(csv_files, save_path, log_path):
    EPOCHS = 100
    WARMUP = 5
    PATIENCE = 20
    
    save_path.mkdir(parents=True, exist_ok=True)
    logger, listener = setup_logging(log_path)
    
    train_loader, val_loader = load_dataloader(csv_files)
    logger.info("Train batches: %d | Val batches: %d", len(train_loader), len(val_loader))

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Using device: %s", device)
    
    # Pass token to model
    token = os.getenv("HF_TOKEN", None)
    model = BiomassModel(token=token)
    model = model.to(device)
    optimizer = build_optimizer(model)
    criterion = BiomassLoss(device)
    ema = ModelEmaV2(model, decay=0.99)

    logger.info("Total parameters: %d", sum(p.numel() for p in model.parameters()))
    logger.info("Total trainable parameters: %d", sum(p.numel() for p in model.parameters() if p.requires_grad))

    if isinstance(model.backbone, PeftModel):
        logger.info("--- PEFT Trainable Parameters ---")
        model.backbone.print_trainable_parameters()
    else:
        logger.warning("Model's backbone is not a PeftModel instance.")
    
    scheduler_warmup = LinearLR(optimizer, start_factor=0.01, end_factor=1.0, total_iters=WARMUP*len(train_loader))
    scheduler_plateau = ReduceLROnPlateau(optimizer, mode='max', factor=0.1, patience=5)
    best_score = -np.inf
    best_e = 0
    start_epoch = 0

    # Resume logic
    last_ckpt_path = save_path / "last_checkpoint.pth"
    if last_ckpt_path.exists():
        logger.info("[*] Found checkpoint at %s. Resuming training...", last_ckpt_path)
        checkpoint = torch.load(last_ckpt_path, map_location=device, weights_only=False)
        model.load_state_dict(checkpoint['model_state_dict'])
        optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        ema.module.load_state_dict(checkpoint['ema_state_dict'])
        scheduler_warmup.load_state_dict(checkpoint['scheduler_warmup_state_dict'])
        scheduler_plateau.load_state_dict(checkpoint['scheduler_plateau_state_dict'])
        start_epoch = checkpoint['epoch'] + 1
        best_score = checkpoint['best_score']
        best_e = checkpoint['best_e']
        logger.info("[*] Resumed at epoch %d (Best BR2: %.4f)", start_epoch, best_score)
        
    for e in range(start_epoch, EPOCHS):
        all_loss = _train(model, train_loader, criterion, optimizer, scheduler_warmup, ema, device, e, WARMUP)
        
        mae, global_score, score, score_per, balanced_score = _eval(ema.module, val_loader, device)
        
        if e >= WARMUP:
            scheduler_plateau.step(balanced_score)
            
        lr_backbone = optimizer.param_groups[0]['lr']
        lr_heads = optimizer.param_groups[1]['lr']

        logger.info("Epoch %d/%d | Loss: %s | MAE: %s | GR2: %.4f | BR2: %.4f",
                    e+1, EPOCHS, all_loss, mae, global_score, balanced_score)
        logger.info("Per R2: %s | LR Backbone: %.7f | LR Heads: %.7f",
                    score_per, lr_backbone, lr_heads)

        # ---- best score tracking & best model checkpoint ----
        if balanced_score > best_score:
            best_e = e
            best_score = balanced_score
            logger.info("[+] Save best model at epoch %d with BR2: %.4f", e+1, best_score)
            save_checkpoint(save_path / "best.bin", model)
            save_checkpoint(save_path / "best_ema.bin", ema.module)

        # ---- CSV logging (no bloqueante, append) ----
        csv_path = log_path / "metrics.csv"
        is_new = not csv_path.exists()
        mejor_str = f"Epoca {best_e+1} (BR2: {best_score:.4f})" if best_score != -np.inf else ""
        row = {
            "Epoch": e + 1,
            "Train_Loss": round(float(np.mean(all_loss)), 5),
            "Val_MAE": round(float(np.mean(mae)), 5),
            "BR2": round(float(balanced_score), 4),
            "GR2": round(float(global_score), 4),
            "R2_Green": round(float(score_per[0]), 4),
            "R2_Dead":  round(float(score_per[1]), 4),
            "R2_Clover": round(float(score_per[2]), 4),
            "LR_Backbone": lr_backbone,
            "LR_Heads": lr_heads,
            "Mejor_Resultado_Hasta_Ahora": mejor_str,
        }
        with open(csv_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            if is_new:
                writer.writeheader()
            writer.writerow(row)

        # Save last checkpoint for resuming
        torch.save({
            'epoch': e,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'ema_state_dict': ema.module.state_dict(),
            'scheduler_warmup_state_dict': scheduler_warmup.state_dict(),
            'scheduler_plateau_state_dict': scheduler_plateau.state_dict(),
            'best_score': best_score,
            'best_e': best_e
        }, save_path / "last_checkpoint.pth")
            
        if e == EPOCHS - 1 or e - best_e >= PATIENCE:
            logger.info("Final epoch, saving model...")
            save_checkpoint(save_path / "final.bin", model )
            save_checkpoint(save_path / "final_ema.bin", ema.module )
            listener.stop()
            return
    
    listener.stop()
    
if __name__ == "__main__":
    ds_path = pathlib.Path("./datasets/fold_news1")
    ckpt_path = pathlib.Path("./checkpoints/ver0/")
    ckpt_path.mkdir(parents=True, exist_ok=True)
    logs_master = pathlib.Path("./logs/ver0/")
    logs_master.mkdir(parents=True, exist_ok=True)
    num_folds = len(os.listdir(ds_path))
    for i in range(num_folds):
        df_path = ds_path / f"fold_{i}.csv"
        save_path = ckpt_path / f"fold_{i}/"
        log_path = logs_master / f"fold_{i}/"
        main(df_path, save_path, log_path)
