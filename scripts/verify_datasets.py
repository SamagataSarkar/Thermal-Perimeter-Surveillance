import os
import yaml

base_dir = os.path.join("datasets", "raw_downloads")
folders = [
    "flir camera objects.v1-release-640.yolov11",
    "thermal-drone.v11i.yolov11"
]

print("=== DATASET VERIFICATION ===")
for folder in folders:
    folder_path = os.path.join(base_dir, folder)
    yaml_path = os.path.join(folder_path, "data.yaml")
    
    if not os.path.exists(yaml_path):
        print(f"[FAIL] Missing data.yaml in {folder}")
        continue
        
    with open(yaml_path, 'r') as f:
        config = yaml.safe_load(f)
        
    train_imgs = len(os.listdir(os.path.join(folder_path, "train", "images"))) if os.path.exists(os.path.join(folder_path, "train", "images")) else 0
    val_imgs = len(os.listdir(os.path.join(folder_path, "valid", "images"))) if os.path.exists(os.path.join(folder_path, "valid", "images")) else 0
    
    print(f"\nFolder: {folder}")
    print(f"  - Train Images: {train_imgs}")
    print(f"  - Val Images:   {val_imgs}")
    print(f"  - Classes ({config.get('nc', len(config.get('names', [])))}): {config.get('names')}")