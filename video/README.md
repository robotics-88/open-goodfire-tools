# Good Fire, Video

The data product we generate from video is called a splat. This is a visually accurate 3D model useful for human interpretation. Future work is to update this to fuse LiDAR with video, which produces geometrically accurate 3D models that can then be a basis for further analytics.

## Setup

### Install dependencies (Ubuntu instructions)
```
cd open-goodfire-tools/video
sudo ./setup.sh
```

## Gaussian Splat Pipeline

Place your video named `<dataset_name>.mp4` in the folder `video/data/input`. Then run the following:

```
cd open-goodfire-tools/video
source ../.env/bin/activate
python gsplat.py --dataset <dataset_name> -vv --sfm odm
```