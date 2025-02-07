# Drone Data Processing

See more internal documentation [here](https://www.notion.so/robotics88/Data-Processing-Documentation-1212bdc47817801bb5f6ccf8cfeed58e?pvs=4).

This repository may eventually merge with [post-flight](https://github.com/robotics-88/post-flight).

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
- `pip install -r requirements.txt`

## Install R dependencies
- `RCSF`
- `lidR`



# Usage

## Primary Processing Script

run `python process.py --input_location=<directory of pcd files> --output_location=<destination>`. The defaults for these values are `data/input` and `data/output`. The tool will detect all `.pcd` files in the specfied input directory, and populate the output directory with the following data types:

- [X] LAS file
- [X] DEM tif
- [X] Aspect tif
- [X] Slope tif
- [X] Base Canopy Height Model tif
- [X] Segmented LAS file
- [X] Diameter at Breast Height csv


## DBH generation script

Run `python generate_dbh.py -v`. This will load a default segmented `.las` file, calculate the DBH for every tree it can find, and write the result to a file of the same name, with the `.csv` extension.
- `-v`, `-vv`, `--verbosity 1/2`: these flags / args will increase the verbosity of the program and give you more visibility into what its doing. I recommend running with verbosity=1 for the most relevant information
- `--visualize`: this flag will tell the program to pause and visualize every processed tree. This is also a good way to get a sense of what its doing. The program will continue once you close the plot.