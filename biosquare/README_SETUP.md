# CSIRO Biomass Prediction Setup Guide

This guide explains how to set up the environment, prepare data, and run inference for the CSIRO Biomass Prediction model.

## 1. Installation

First, install the required Python dependencies:

```bash
python install_deps.py
```

## 2. Data Preparation

The model requires data in a specific "wide" format (one row per image). The provided script `prepare_data.py` converts the provided `train.csv` and `test.csv` (if present) into `train_wide.csv` and `test_wide.csv`.

```bash
python prepare_data.py
```

## 3. Model Weights

The model uses a `dinov3` backbone from Facebook.

**Option A: Automatic Download**
Run the download script to fetch the backbone config and weights from Hugging Face:

```bash
python download_weights.py
```

> **Note:** The `dinov3` model is gated on Hugging Face. You must have a Hugging Face account, accept the license on the model page (https://huggingface.co/facebook/dinov3-vitl16-pretrain-lvd1689m), and be logged in via `huggingface-cli login` for this to work.

**Option B: Trained Weights**
If you have the fine-tuned weights from the competition, place them in the `checkpoints/ver0/` directory (e.g., `checkpoints/ver0/fold_0/best_ema.bin`). The inference script looks for `.bin` files in this directory.

## 4. Running Inference

To generate predictions on the test set:

```bash
python predict.py --csv test_wide.csv --output submission.csv
```

**Important:**
- If trained weights are found in `checkpoints/ver0`, they are used.
- If no trained weights are found, the script attempts to load the pre-trained backbone.
- If the backbone cannot be accessed (e.g., no Hugging Face login), the script falls back to a **Dummy Model** that generates random predictions. This ensures the pipeline runs, but the results will not be valid.
- Watch the console output to see which model is being used.

## 5. Monitoring Training Metrics

To see the metrics per epoch (R2, MAE, Balanced R2), you should execute the training script:

```bash
python train.py
```

**What to expect:**
- The script will print the metrics directly to the console for each epoch.
- **Metrics shown:** 
  - `Train Loss`: Current loss.
  - `MAE`: Mean Absolute Error.
  - `R2`: Mean R2 score.
  - `BR2`: Balanced R2 score (Primary metric).
  - `Per R2`: R2 score for each component (Green, Dead, Clover).
- **Checkpoints:** The best weights based on the `BR2` score will be saved in `./checkpoints/ver0/fold_X/best_ema.bin`.

## 6. Weight Storage Locations

- **Backbone Weights (Initial)**: These are downloaded from Hugging Face and stored in your user cache directory: `C:\Users\navi\.cache\huggingface\hub`.
- **Fine-tuned Weights (Output)**: These are generated during training and saved in the `./checkpoints/` folder within the project directory.
