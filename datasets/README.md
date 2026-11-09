# Dataset documentation

The repository uses a unified four-class YOLO dataset configuration at
[`unified/data.yaml`](unified/data.yaml):

```yaml
names:
  0: person
  1: vehicle
  2: animal
  3: drone
```

## Metadata currently present

The tracked dataset metadata folders are:

```text
datasets/
├── raw_downloads/
│   ├── flir camera objects.v1-release-640.yolov11/
│   ├── Thermal FLiR.v4i.yolov11/
│   └── thermal-drone.v11i.yolov11/
└── unified/
    └── data.yaml
```

Each raw-download folder contains a dataset YAML file and provider/export
README metadata. The provider information documented by those files is:

| Metadata folder | Provider reference | License stated in metadata |
| --- | --- | --- |
| `flir camera objects.v1-release-640.yolov11` | Roboflow FLIR Camera Objects / RF100 | CC BY 4.0 |
| `Thermal FLiR.v4i.yolov11` | Roboflow Thermal FLiR | CC BY 4.0 |
| `thermal-drone.v11i.yolov11` | Roboflow Thermal Drone | CC BY 4.0 |

Refer to the individual `README.dataset.txt` and `README.roboflow.txt` files
for the source URLs and the attribution text supplied with each export.

## Training data availability

The current GitHub repository contains dataset metadata and configuration, not
the complete training image and label collections. Local workspaces may
contain generated images, labels, caches, or downloaded exports, but those
files should not be assumed to be available after a fresh clone.

Before retraining:

1. Obtain the source datasets from their documented providers.
2. Confirm the provider terms and required attribution.
3. Prepare the images and YOLO labels using the four-class mapping above.
4. Arrange the resulting data under the paths referenced by
   `unified/data.yaml` (`images/train` and `images/valid`, with corresponding
   labels).
5. Verify the prepared dataset before starting training.

The training script is [`../scripts/train_yolo.py`](../scripts/train_yolo.py).
It references the base `yolo11n.pt` checkpoint and trains from
`datasets/unified/data.yaml`; training is separate from Version 1 inference,
which uses the included custom checkpoint under
`../runs/detect/models/thermal_perimeter_yolo11n-2/weights/best.pt`.

Do not download or commit dataset images or labels as part of this
documentation update.
