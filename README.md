# Drone Data Processing

See more internal documentation [here](https://www.notion.so/robotics88/Data-Processing-Documentation-1212bdc47817801bb5f6ccf8cfeed58e?pvs=4)

This repository may eventually merge with [post-flight](https://github.com/robotics-88/post-flight)

# Purpose

This project aims to automate and clean up the data processing of collected `.pcd` files from drone flights.

# Setup

See the above linked documentation for links and notes on dependencies

## Install system dependencies (Ubuntu instructions)
- `sudo apt install python3-venv`

## Create a python virtual environment
- `python -m venv env`
- `source env/bin/activate`

## Install python dependencies
- `pip install laspy numpy argparse`



# Usage

run `python process.py --input_path=<directory of pcd files> --output_path=<destination>`. The defaults for these values are `data/input` and `data/output`. The tool will detect all `.pcd` files in the specfied input directory, and populate the output directory with the following data types:

- [X] LAS file
- [X] DEM tif
- [X] Aspect tif
- [X] Slope tif
- [X] Base Canopy Height Model tif
- [X] Segmented LAS file
- [ ] Diameter at Breast Height csv
