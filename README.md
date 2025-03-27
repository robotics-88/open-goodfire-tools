# Drone Data Processing

See more internal documentation [here](https://www.notion.so/robotics88/Data-Processing-Documentation-1212bdc47817801bb5f6ccf8cfeed58e?pvs=4).
This repository may eventually merge with [post-flight](https://github.com/robotics-88/post-flight).

# Purpose

This produces meaningful data products from raw drone flight data. Currently we can produce:
- [X] LAS file
- [X] DEM tif
- [X] Aspect tif
- [X] Slope tif
- [X] Base Canopy Height Model tif
- [X] Segmented LAS file
- [X] Diameter at Breast Height csv

- [X] Gaussian Splats (from video data)
- [ ] PCD

# Setup

## Install dependencies (Ubuntu instructions)
- `sudo ./setup.sh`

## Install R dependencies
- `RCSF`
- `lidR`



# Usage
There are currently two distinct pipelines. In the future, we will merge these into something more cohesive

## Gaussian Splat Pipeline

Place your video named `<dataset_name>.mp4` in the folder `gsplat_data/input`. Then run the following:

```
./.env/bin/activate
python gsplat.py --dataset <dataset_name> -vv --sfm odm
```


## PCD Pipeline

Place your pcd files named `<dataset_name>_<crs_code>.pdf` in the folder `data/input`. The run the following:

```
./.env/bin/activate
python process.py -vv
```