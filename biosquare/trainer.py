import csv
import logging

import numpy as np
import pandas as pd
import torch
import torch.optim as optim
import tqdm
from timm.utils import ModelEmaV2
from torch.optim.lr_scheduler import LinearLR, ReduceLROnPlateau
from torch.utils.data import DataLoader
from peft import PeftModel

from config import Config
from checkpoint import save_checkpoint, save_model_weights, load_checkpoint
from dataset import BiomassDataset, compute_scales
from loss import BiomassLoss
from metrics import (
    compute_regression_metrics,
    get_balance_metric,
    postprocess,
    weighted_r2_score_global,
)
from model import BiomassModel
from transforms import get_train_transforms, get_valid_transforms

AMP_DTYPES = {
    "float16": torch.float16,
    "bfloat16": torch.bfloat16,
    "float32": torch.float32,
}


class Trainer:
    def __init__(self, config: Config, csv_path, save_path, log_path, token=None):
        self.cfg = config
        self.csv_path = csv_path
        self.save_path = save_path
        self.log_path = log_path
        self.logger = logging.getLogger("biomass")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.amp_dtype = AMP_DTYPES.get(config.amp_dtype, torch.float16)

        self.train_loader, self.val_loader, self.scales = self._build_dataloaders()
        self.model = BiomassModel(token=token).to(self.device)
        self.model.scales.copy_(self.scales.to(self.device))
        self.ema = ModelEmaV2(self.model, decay=self.cfg.ema_decay)
        self.optimizer = self._build_optimizer()
        self.criterion = BiomassLoss(self.device)
        self.scaler = torch.amp.GradScaler('cuda', enabled=self.device.type != 'cpu')

    def _build_dataloaders(self):
        df = pd.read_csv(self.csv_path)
        train_df = df[df["split"] == "train"]
        val_df = df[df["split"] != "train"]
        scales = compute_scales(train_df)
        train_ds = BiomassDataset(train_df, transform=get_train_transforms(self.cfg.img_size), scales=scales)
        val_ds = BiomassDataset(val_df, transform=get_valid_transforms(self.cfg.img_size), scales=scales)
        train_loader = DataLoader(
            train_ds, batch_size=self.cfg.batch_size, shuffle=True,
            num_workers=self.cfg.num_workers, pin_memory=True, drop_last=True,
        )
        dropped = len(train_ds) - len(train_loader) * self.cfg.batch_size
        if dropped > 0:
            self.logger.info("drop_last descarta %d muestra(s) de train", dropped)
        val_loader = DataLoader(
            val_ds, batch_size=self.cfg.batch_size, shuffle=False,
            num_workers=self.cfg.num_workers, pin_memory=True, drop_last=False,
        )
        return train_loader, val_loader, scales

    def _build_optimizer(self):
        return optim.AdamW([
            {
                'params': self.model.backbone.parameters(),
                'lr': self.cfg.lr_backbone,
                'weight_decay': self.cfg.weight_decay,
            },
            {
                'params': self.model.heads.parameters(),
                'lr': self.cfg.lr_heads,
                'weight_decay': self.cfg.weight_decay,
            },
        ])

    def _train_step(self, epoch):
        self.model.train()
        all_loss = []
        self.optimizer.zero_grad()
        debug = self.logger.isEnabledFor(logging.DEBUG)
        for idx, (img, labels) in (pbar := tqdm.tqdm(enumerate(self.train_loader), total=len(self.train_loader))):
            if debug:
                self.logger.debug("Batch %d | Shapes: %s %s", idx, img.shape, labels.shape)
            img = img.to(self.device)
            labels = labels.to(self.device)
            autocast = torch.autocast(
                self.device.type, dtype=self.amp_dtype, enabled=self.device.type != 'cpu'
            )
            with autocast:
                preds = self.model(img)
            loss, loss_full = self.criterion(preds, labels)
            loss = loss / self.cfg.accumulation_steps
            if self.scaler is not None:
                self.scaler.scale(loss).backward()
            else:
                loss.backward()

            if (idx + 1) % self.cfg.accumulation_steps == 0 or idx == len(self.train_loader) - 1:
                if self.scaler is not None:
                    self.scaler.unscale_(self.optimizer)
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.cfg.grad_clip)
                if self.scaler is not None:
                    self.scaler.step(self.optimizer)
                    self.scaler.update()
                else:
                    self.optimizer.step()
                self.optimizer.zero_grad()
                self.ema.update(self.model)
                if epoch < self.cfg.warmup:
                    self.scheduler_warmup.step()

            pbar.set_postfix({'loss': loss.item() * self.cfg.accumulation_steps})
            loss_weights = self.criterion.weights.detach().cpu().numpy()
            weighted_loss = float(np.dot([j.detach().cpu().item() for j in loss_full], loss_weights))
            all_loss.append(weighted_loss)
        return float(np.mean(all_loss))

    def _evaluate(self):
        all_pred = []
        all_labels = []
        self.ema.module.eval()
        with torch.no_grad():
            for img, labels in tqdm.tqdm(self.val_loader, total=len(self.val_loader), leave=False):
                img = img.to(self.device, dtype=torch.float32)
                preds = self.ema.module(img)
                preds = torch.stack(preds, -1).cpu().numpy()
                all_pred.append(preds)
                all_labels.append(labels.numpy())

        all_pred = np.concatenate(all_pred, 0)
        all_pred = postprocess(all_pred, is_gt=False, scales=self.ema.module.scales)
        all_labels = np.concatenate(all_labels, 0)
        all_labels = postprocess(all_labels, is_gt=True, scales=self.ema.module.scales)

        mae, rmse, rmsle, mae_bucket = compute_regression_metrics(all_labels, all_pred)
        global_score, score, score_per = weighted_r2_score_global(all_labels, all_pred)
        balanced_score = get_balance_metric(score_per[:3])
        score_per = [round(float(s), 4) for s in score_per]
        return mae, rmse, rmsle, mae_bucket, global_score, score, score_per, balanced_score

    def _log_epoch(self, e, train_loss, mae, rmse, rmsle, mae_bucket, global_score, score_per, balanced_score, best_score, best_e):
        self.logger.info("Epoch %d/%d | Loss: %.5f | BR2: %.4f | GR2: %.4f",
                         e + 1, self.cfg.epochs, train_loss, balanced_score, global_score)
        self.logger.info("MAE  - Green: %.4f | Dead: %.4f | Total: %.4f", mae[0], mae[1], mae[2])
        self.logger.info("RMSE - Green: %.4f | Dead: %.4f | Total: %.4f", rmse[0], rmse[1], rmse[2])
        self.logger.info("RMSLE- Green: %.4f | Dead: %.4f | Total: %.4f", rmsle[0], rmsle[1], rmsle[2])
        for tgt in ("Green", "Dead", "Total"):
            self.logger.info(
                "MAE %-5s - 0g: %.4f | 0-5: %.4f | 5-15: %.4f | 15-30: %.4f | 30+: %.4f",
                tgt, mae_bucket[f"{tgt}_0g"], mae_bucket[f"{tgt}_0_5g"],
                mae_bucket[f"{tgt}_5_15g"], mae_bucket[f"{tgt}_15_30g"], mae_bucket[f"{tgt}_30+"],
            )
        self.logger.info("R2  - Green: %.4f | Dead: %.4f | Total: %.4f | LR Bk: %.7f | LR Hd: %.7f",
                         score_per[0], score_per[1], score_per[2],
                         self.optimizer.param_groups[0]['lr'], self.optimizer.param_groups[1]['lr'])

        row = {
            "Epoch": e + 1,
            "Train_Loss": round(float(train_loss), 5),
            "Val_MAE": round(float(np.mean(mae)), 5),
            "BR2": round(float(balanced_score), 4),
            "GR2": round(float(global_score), 4),
            "R2_Green": round(float(score_per[0]), 4),
            "R2_Dead": round(float(score_per[1]), 4),
            "R2_Total": round(float(score_per[2]), 4),
            "MAE_Green": round(float(mae[0]), 4),
            "MAE_Dead": round(float(mae[1]), 4),
            "MAE_Total": round(float(mae[2]), 4),
            "RMSE_Green": round(float(rmse[0]), 4),
            "RMSE_Dead": round(float(rmse[1]), 4),
            "RMSE_Total": round(float(rmse[2]), 4),
            "RMSLE_Green": round(float(rmsle[0]), 4),
            "RMSLE_Dead": round(float(rmsle[1]), 4),
            "RMSLE_Total": round(float(rmsle[2]), 4),
        }
        for tgt in ("Green", "Dead", "Total"):
            for bucket in ("0g", "0_5g", "5_15g", "15_30g", "30+"):
                row[f"MAE_{tgt}_{bucket}"] = round(mae_bucket[f"{tgt}_{bucket}"], 4)
        row["LR_Backbone"] = self.optimizer.param_groups[0]['lr']
        row["LR_Heads"] = self.optimizer.param_groups[1]['lr']
        row["Mejor_Resultado_Hasta_Ahora"] = (
            f"Epoca {best_e + 1} (BR2: {best_score:.4f})" if best_score != -np.inf else ""
        )
        self._write_csv(row)

    def _write_csv(self, row):
        csv_path = self.log_path / "metrics.csv"
        is_new = not csv_path.exists()
        with open(csv_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            if is_new:
                writer.writeheader()
            writer.writerow(row)

    def fit(self):
        cfg = self.cfg
        logger = self.logger
        logger.info("Train batches: %d | Val batches: %d", len(self.train_loader), len(self.val_loader))
        logger.info("Using device: %s", self.device)
        logger.info("Total parameters: %d", sum(p.numel() for p in self.model.parameters()))
        logger.info("Total trainable parameters: %d",
                    sum(p.numel() for p in self.model.parameters() if p.requires_grad))

        if isinstance(self.model.backbone, PeftModel):
            logger.info("--- PEFT Trainable Parameters ---")
            self.model.backbone.print_trainable_parameters()
        else:
            logger.warning("Model's backbone is not a PeftModel instance.")

        steps_per_epoch = (len(self.train_loader) + cfg.accumulation_steps - 1) // cfg.accumulation_steps
        self.scheduler_warmup = LinearLR(self.optimizer, start_factor=0.01, end_factor=1.0,
                                         total_iters=cfg.warmup * steps_per_epoch)
        self.scheduler_plateau = ReduceLROnPlateau(self.optimizer, mode='max', factor=0.1, patience=5)
        schedulers = {"scheduler_warmup": self.scheduler_warmup, "scheduler_plateau": self.scheduler_plateau}

        best_score = -np.inf
        best_e = 0
        start_epoch = 0

        last_ckpt_path = self.save_path / "last_checkpoint.pth"
        if last_ckpt_path.exists():
            logger.info("[*] Found checkpoint at %s. Resuming training...", last_ckpt_path)
            state = load_checkpoint(last_ckpt_path, self.model, self.ema, self.optimizer,
                                    schedulers, self.scaler, self.device)
            start_epoch = state['epoch'] + 1
            best_score = state['best_score']
            best_e = state['best_e']
            logger.info("[*] Resumed at epoch %d (Best BR2: %.4f)", start_epoch, best_score)

        if start_epoch == 0:
            self.model.scales.copy_(self.scales.to(self.device))
            self.ema.module.scales.copy_(self.scales.to(self.device))
        logger.info("Normalization scales: green %.2f | dead %.2f", self.scales[0], self.scales[1])

        e = start_epoch - 1
        try:
            for e in range(start_epoch, cfg.epochs):
                train_loss = self._train_step(e)
                mae, rmse, rmsle, mae_bucket, global_score, score, score_per, balanced_score = self._evaluate()

                if e >= cfg.warmup:
                    self.scheduler_plateau.step(balanced_score)

                if balanced_score > best_score:
                    best_e = e
                    best_score = balanced_score
                    logger.info("[+] Save best model at epoch %d with BR2: %.4f", e + 1, best_score)
                    save_model_weights(self.save_path / "best_ema.pt", self.ema.module)

                self._log_epoch(e, train_loss, mae, rmse, rmsle, mae_bucket,
                                global_score, score_per, balanced_score, best_score, best_e)

                save_checkpoint(last_ckpt_path, e, self.model, self.ema, self.optimizer,
                                schedulers, self.scaler, best_score, best_e)

                if e == cfg.epochs - 1 or e - best_e >= cfg.patience:
                    logger.info("Final epoch, saving model...")
                    save_model_weights(self.save_path / "final_ema.pt", self.ema.module)
                    return
        except KeyboardInterrupt:
            logger.warning("Interrupción detectada. Guardando checkpoint para reanudar...")
            save_checkpoint(last_ckpt_path, e, self.model, self.ema, self.optimizer,
                            schedulers, self.scaler, best_score, best_e)
            logger.warning("Checkpoint guardado. Saliendo...")
            raise
        except Exception:
            logger.exception("Error durante el entrenamiento. Guardando checkpoint para reanudar...")
            save_checkpoint(last_ckpt_path, e, self.model, self.ema, self.optimizer,
                            schedulers, self.scaler, best_score, best_e)
            raise
