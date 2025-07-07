# Good Fire, LiDAR

This package processes georegistered LiDAR in las or laz format into data for good fire, including:
- [X] DEM tif
- [X] Aspect tif
- [X] Slope tif
- [X] Base Canopy Height Model tif
- [X] Tree ID LAS file
- [X] Diameter at Breast Height csv

## LAZ Pipeline

Place your laz file/s in the folder `data/input/<mydataset>/before`. Use this folder regardless of whether there is a corresponding before/after fire dataset. However, if there is a before and after, put the after-fire dataset in `data/input/<mydataset>/after`. If this folder doesn't exist or is empty, the script will just run the analytics that don't require before and after.

TODO: If there is a single laz file in `before/`, the script will segment it first into tiles. If there is a corresponding `after/`, the script will clip both datasets to the overlapping section and produce corresponding tiles.

## Setup

### Install dependencies (Ubuntu instructions)
```
cd open-goodfire-tools/lidar
sudo ./setup.sh
```

## Usage
Run the following:

```
cd open-goodfire-tools/lidar
source ../.env/bin/activate
python process.py -vv --name mydataset
```