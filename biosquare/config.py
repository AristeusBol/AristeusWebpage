import pathlib
from dataclasses import dataclass, field


@dataclass
class Config:
    # Entrenamiento
    epochs: int = 100
    warmup: int = 5
    patience: int = 20
    accumulation_steps: int = 4
    batch_size: int = 2
    lr_backbone: float = 1e-4
    lr_heads: float = 1e-3
    weight_decay: float = 1e-3
    grad_clip: float = 1.0
    ema_decay: float = 0.99
    amp_dtype: str = "float16"
    seed: int = 16999

    # Datos
    img_size: tuple = (1024, 1024)
    num_workers: int = 4

    # Loss
    loss_weights: tuple = (0.4, 0.6)
    tweedie_p: float = 1.2

    # TTA (predict)
    tta_weights: tuple = (0.4, 0.2, 0.2, 0.2)

    # Rutas
    data_dir: pathlib.Path = pathlib.Path("./data")
    checkpoints_dir: pathlib.Path = pathlib.Path("./checkpoints")
    logs_dir: pathlib.Path = pathlib.Path("./logs")
    backbone_dir: pathlib.Path = pathlib.Path("./backbone_weights")
    folds_dir: pathlib.Path = None
    version: str = "v1"

    def __post_init__(self):
        if self.folds_dir is None:
            self.folds_dir = self.data_dir / "folds" / "folds_v1"
        self.data_dir = pathlib.Path(self.data_dir)
        self.checkpoints_dir = pathlib.Path(self.checkpoints_dir)
        self.logs_dir = pathlib.Path(self.logs_dir)
        self.backbone_dir = pathlib.Path(self.backbone_dir)
        self.folds_dir = pathlib.Path(self.folds_dir)

    def fold_checkpoints_dir(self, fold_id: str) -> pathlib.Path:
        return self.checkpoints_dir / self.version / f"fold_{fold_id}"

    def fold_logs_dir(self, fold_id: str) -> pathlib.Path:
        return self.logs_dir / self.version / f"fold_{fold_id}"
