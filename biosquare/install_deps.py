import subprocess
import sys

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

required_packages = [
    "torch",
    "timm",
    "transformers",
    "torchao>=0.16.0",
    "peft",
    "pandas",
    "albumentations",
    "opencv-python"
]

def main():
    print("Installing required packages...")
    for package in required_packages:
        try:
            print(f"Installing {package}...")
            install(package)
            print(f"Successfully installed {package}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to install {package}. Error: {e}")
            # Continue installing other packages even if one fails
            continue

if __name__ == "__main__":
    main()
