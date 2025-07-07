# Open Good Fire Tools

This repo contains tools for processing LiDAR (las/laz format) or video into good fire analytics. The workflows for each are separate. Details for each are below.

> [!NOTE] 
> We strive to keep this README up to date, but for the latest, see the postflight analytics section of our [open drone docs](https://robotics-88.github.io/open-drone-docs/).

# Purpose

This produces meaningful data products from raw drone flight data. Currently we can produce:

## From LiDAR
- [X] DEM tif
- [X] Aspect tif
- [X] Slope tif
- [X] Base Canopy Height Model tif
- [X] Tree ID LAS file
- [X] Diameter at Breast Height csv

## From video
- [X] Gaussian Splats
- [ ] PCD

# Setup

We provide separate setup and instructions for each workflow. See [LiDAR](lidar/README.md) and [video](video/README.md) for more details.
