import cv2
import glob
import os

def create_thermal_demo_video(image_folder, output_path="demo_thermal.mp4", fps=5):
    images = sorted(glob.glob(os.path.join(image_folder, "flir_*.jpg")))
    
    if not images:
        images = sorted(glob.glob(os.path.join(image_folder, "*.jpg")))

    if not images:
        print(f"No images found in {image_folder}")
        return

    # Select a continuous block of 300 to 500 frames for a realistic demo clip
    selected_frames = images[:400]
    first_frame = cv2.imread(selected_frames[0])
    h, w, _ = first_frame.shape

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    print(f"Stitching {len(selected_frames)} thermal frames into '{output_path}'...")
    for img_path in selected_frames:
        frame = cv2.imread(img_path)
        out.write(frame)

    out.release()
    print(f"Video saved successfully as {output_path}")

if __name__ == "__main__":
    create_thermal_demo_video("datasets/unified/images/valid")