import torch.nn as nn
import torch
import torch.nn.functional as F
import os
from transformers import AutoModel
from peft import get_peft_model, LoraConfig
from dataset import DEFAULT_SCALES


def load_lora_backbone(token=None):
    local_path = "./backbone_weights"
    model_name = "facebook/dinov3-vitl16-pretrain-lvd1689m"
    
    if os.path.exists(os.path.join(local_path, "config.json")):
        print(f"Loading backbone from local path: {local_path}")
        model = AutoModel.from_pretrained(local_path)
    else:
        if token is None:
            token = os.getenv("HF_TOKEN")
            print(f"Loading backbone from Hugging Face: {model_name}")
        model = AutoModel.from_pretrained(
            model_name,
            token=token
        )
    
    peft_config = LoraConfig(
        r=32,
        lora_alpha=64,
        target_modules=["k_proj", "v_proj", "q_proj", "o_proj"],
        lora_dropout=0.01, 
        use_dora=True,
        bias="none",
    )
    lora_model = get_peft_model(model, peft_config)
    return lora_model


class LocalMambaBlock(nn.Module):
    def __init__(self, dim, kernel_size=5, dropout=0.0):
        super().__init__()
        self.norm = nn.LayerNorm(dim)
        self.dwconv = nn.Conv1d(
            dim, dim, kernel_size=kernel_size, padding=kernel_size // 2, groups=dim
        )
        self.gate = nn.Linear(dim, dim)
        self.proj = nn.Linear(dim, dim)
        self.drop = nn.Dropout(dropout)

    def forward(self, x):
        shortcut = x
        B, N, D = x.shape
        x = self.norm(x)
        g = torch.sigmoid(self.gate(x))
        x = x * g
        x = x.transpose(1, 2)
        x = self.dwconv(x)
        x = x.transpose(1, 2)
        x = self.proj(x)
        x = self.drop(x)
        return shortcut + x


class PositiveActivation(nn.Module):
    def __init__(self, floor=0.001):
        super().__init__()
        self.floor = floor

    def forward(self, x):
        return F.elu(x) + 1.0 + self.floor


class RegressionHead(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.fusion = nn.Sequential(
            LocalMambaBlock(dim, kernel_size=5, dropout=0.1),
            LocalMambaBlock(dim, kernel_size=5, dropout=0.1),
        )
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.head_green_raw = nn.Sequential(
            nn.Linear(dim, dim // 2),
            nn.GELU(),
            nn.Dropout(0.2),
            nn.Linear(dim // 2, 1),
            PositiveActivation(),
        )
        self.head_dead_raw = nn.Sequential(
            nn.Linear(dim, dim // 2),
            nn.GELU(),
            nn.Dropout(0.2),
            nn.Linear(dim // 2, 1),
            PositiveActivation(),
        )

    def forward(self, x):
        x_fused = self.fusion(x)
        x_pool = self.pool(x_fused.transpose(1, 2)).flatten(1)
        green = self.head_green_raw(x_pool)
        dead = self.head_dead_raw(x_pool)
        return (
            green.squeeze(-1),
            dead.squeeze(-1),
        )


class BiomassModel(nn.Module):
    def __init__(self, token=None, img_size=1024, patch_size=16):
        super().__init__()
        if img_size % patch_size != 0:
            raise ValueError(f"img_size ({img_size}) must be divisible by patch_size ({patch_size})")
        self.img_size = img_size
        self.patch_size = patch_size
        self.register_buffer("scales", DEFAULT_SCALES.clone())
        self.backbone = load_lora_backbone(token=token)
        nf = self.backbone.config.hidden_size
        self.heads = RegressionHead(nf)
        self.num_prefix = 1 + self.backbone.config.num_register_tokens

    def forward(self, img):
        x = self.backbone(img).last_hidden_state[:, self.num_prefix:]
        return self.heads(x)