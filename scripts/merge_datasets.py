import os
import shutil
import glob
from tqdm import tqdm

BASE_RAW = os.path.join("datasets", "raw_downloads")
OUT_DIR = os.path.join("datasets", "unified")

FLIR_DIR = os.path.join(BASE_RAW, "flir camera objects.v1-release-640.yolov11")
DRONE_DIR = os.path.join(BASE_RAW, "thermal-drone.v11i.yolov11")

# Explicit class mappings derived from verification output
FLIR_MAP = {
    0: 1,  # bicycle -> vehicle
    1: 1,  # car     -> vehicle
    2: 2,  # dog     -> animal
    3: 0   # person  -> person
}

DRONE_MAP = {
    0: 3,  # '0'           -> drone
    1: 3,  # 'DJI-Phantom' -> drone
    2: 3,  # 'DRONE'       -> drone
    3: 3,  # 'drone-thermal'-> drone
    4: 3,  # 'fpv-drone'   -> drone
    5: 3   # 'ufo-thermal' -> drone
}

def resolve_split_path(source_dir, split_name):
    """Finds either 'val' or 'valid' directory depending on Roboflow naming."""
    for variant in [split_name, "val", "valid"]:
        candidate = os.path.join(source_dir, variant)
        if os.path.exists(candidate):
            return candidate
    return None

def process_and_merge(source_dir, split_key, target_split, remap_dict, prefix):
    src_split_folder = resolve_split_path(source_dir, split_key)
    if not src_split_folder:
        print(f"[WARN] Split {split_key} not found in {source_dir}")
        return

    src_img_dir = os.path.join(src_split_folder, "images")
    src_lbl_dir = os.path.join(src_split_folder, "labels")

    dst_img_dir = os.path.join(OUT_DIR, "images", target_split)
    dst_lbl_dir = os.path.join(OUT_DIR, "labels", target_split)
    os.makedirs(dst_img_dir, exist_ok=True)
    os.makedirs(dst_lbl_dir, exist_ok=True)

    label_files = glob.glob(os.path.join(src_lbl_dir, "*.txt"))
    print(f"Processing {prefix} [{target_split}] - {len(label_files)} label files...")

    for lbl_path in tqdm(label_files):
        base_name = os.path.splitext(os.path.basename(lbl_path))[0]
        
        # Match image with any standard extension
        matching_imgs = glob.glob(os.path.join(src_img_dir, f"{base_name}.*"))
        if not matching_imgs:
            continue

        remapped_lines = []
        with open(lbl_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if not parts:
                    continue
                old_cls = int(parts[0])
                if old_cls in remap_dict:
                    parts[0] = str(remap_dict[old_cls])
                    remapped_lines.append(" ".join(parts))

        # Only copy if valid objects remain
        if remapped_lines:
            target_name = f"{prefix}_{base_name}"
            # Write standardized label
            with open(os.path.join(dst_lbl_dir, f"{target_name}.txt"), "w", encoding="utf-8") as out_f:
                out_f.write("\n".join(remapped_lines) + "\n")
            
            # Copy corresponding image
            img_ext = os.path.splitext(matching_imgs[0])[1]
            shutil.copy2(matching_imgs[0], os.path.join(dst_img_dir, f"{target_name}{img_ext}"))

if __name__ == "__main__":
    splits = [("train", "train"), ("val", "valid")]
    
    for src_split, target_split in splits:
        process_and_merge(FLIR_DIR, src_split, target_split, FLIR_MAP, "flir")
        process_and_merge(DRONE_DIR, src_split, target_split, DRONE_MAP, "drone")
        
    print("\nDataset unification complete inside 'datasets/unified/'.")