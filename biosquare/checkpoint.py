import logging

import torch

logger = logging.getLogger("biomass")


def save_checkpoint(path, epoch, model, ema, optimizer, schedulers, scaler=None, best_score=None, best_e=None):
    state = {
        'epoch': epoch,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'ema_state_dict': ema.module.state_dict(),
        'best_score': best_score,
        'best_e': best_e,
    }
    for key, scheduler in schedulers.items():
        state[f'{key}_state_dict'] = scheduler.state_dict()
    if scaler is not None:
        state['scaler_state_dict'] = scaler.state_dict()
    torch.save(state, path)


def save_model_weights(path, model):
    torch.save(model.state_dict(), path)


def load_checkpoint(path, model, ema, optimizer, schedulers, scaler=None, device=None):
    checkpoint = torch.load(path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint['model_state_dict'])
    optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
    ema.module.load_state_dict(checkpoint['ema_state_dict'])
    for key, scheduler in schedulers.items():
        scheduler.load_state_dict(checkpoint[f'{key}_state_dict'])
    if scaler is not None and 'scaler_state_dict' in checkpoint:
        scaler.load_state_dict(checkpoint['scaler_state_dict'])
    return {
        'epoch': checkpoint['epoch'],
        'best_score': checkpoint.get('best_score'),
        'best_e': checkpoint.get('best_e'),
    }
