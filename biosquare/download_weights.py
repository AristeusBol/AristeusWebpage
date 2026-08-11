from transformers import AutoModel, AutoConfig
import os

def download_backbone(token=None):
    model_name = "facebook/dinov3-vitl16-pretrain-lvd1689m"
    if token is None:
        token = os.getenv("HF_TOKEN", True)
    
    save_dir = "./backbone_weights"
    os.makedirs(save_dir, exist_ok=True)
    
    print(f"Downloading backbone model ({model_name}) to {save_dir}...")
    try:
        # Download and save locally
        config = AutoConfig.from_pretrained(model_name, token=token)
        config.save_pretrained(save_dir)
        
        model = AutoModel.from_pretrained(model_name, token=token)
        model.save_pretrained(save_dir)
        
        print(f"Backbone model downloaded and saved successfully to {save_dir}")
    except Exception as e:
        print(f"Failed to download backbone model. Error: {e}")
        print("\nTIP: Make sure your token is valid and you have accepted the license on Hugging Face.")

if __name__ == "__main__":
    import sys
    hf_token = sys.argv[1] if len(sys.argv) > 1 else None
    download_backbone(hf_token)
