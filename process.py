import generate_dbh
import utils.argument_actions

import argparse
import subprocess
from pathlib import Path

from fastlog import log


log_level_options = [log.WARNING, log.INFO, log.DEBUG]


def split_inputs():
    # TODO: accept a pcd or las and split it into multiple tiled subcomponents
    pass

def generate_las(pcd_path, las_path):
    # Use pdal command to generate las. call blocks until command finishes.
    return subprocess.call(['pdal', 'translate', pcd_path, las_path])

def generate_dem(las_path, dem_path):
    # Use Rscript command to generate las.
    # Optionally, overwrite the existing dem with -o
    # TODO: restructure R scripts to accept python style arguments
    return subprocess.call(['./generate_dem.R', las_path, dem_path])
    
def generate_slope(dem_path, slope_path):
    # Use gdal command to generate slope. call blocks until command finishes.
    return subprocess.call(['gdaldem', 'slope', dem_path, slope_path])

def generate_aspect(dem_path, aspect_path):
    # Use gdal command to generate aspect. call blocks until command finishes.
    return subprocess.call(['gdaldem', 'aspect', dem_path, aspect_path])

def generate_base_canopy_height_model(las_path, chm_path):
    return subprocess.call(['./generate_chm.R', las_path, chm_path])
    
def generate_segmented_las(las_path, chm_path, las_segmented_path):
    return subprocess.call(['./segment_las.R', las_path, chm_path, las_segmented_path])

def generate_diameter_at_base_height(las_segmented_path, chm_path,  dem_path, dbh_path):
    # TODO: write a script to consume segmented LAS data, and compute dbh. Start in R.
    generate_dbh.generate_dbh(las_segmented_path, chm_path,  dem_path, dbh_path)



if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--input_location', action=utils.argument_actions.StorePathAction, default=Path('data/input'))
    parser.add_argument('--output_location', action=utils.argument_actions.StorePathAction, default=Path('data/output'))

    parser.add_argument('-v', action='count')
    parser.add_argument('--verbosity', type=int, default=1)
    
    args = parser.parse_args()

    # Process verbosity args
    verbosity = args.v if args.v else args.verbosity
    verbosity = min(verbosity, len(log_level_options)-1)
    log.setLevel(log_level_options[verbosity])

    for file in args.input_location.glob('**/*.pcd'):
        pcd_path = file

        output_directory = args.output_location / file.stem
        output_directory.mkdir(parents=True, exist_ok=True)


        las_path = (output_directory / file.stem).with_suffix('.las')
        log.info(f'Generating las file at {las_path}')
        generate_las(pcd_path, las_path)
        
        dem_path = las_path.with_name(file.stem + '_dem.tif')
        log.info(f'Generating dem file at {dem_path}')
        generate_dem(las_path, dem_path)
        
        slope_path = las_path.with_name(file.stem + '_slope.tif')
        aspect_path = las_path.with_name(file.stem + '_aspect.tif')
        log.info(f'Generating slope file at {slope_path}')
        generate_slope(dem_path, slope_path)
        log.info(f'Generating aspect file at {aspect_path}')
        generate_aspect(dem_path, aspect_path)

        chm_path = las_path.with_name(file.stem + '_chm.tif')
        log.info(f'Generating chm file at {chm_path}')
        generate_base_canopy_height_model(las_path, chm_path)

        las_segmented_path = las_path.with_name(file.stem + '_segmented.las')
        log.info(f'Generating segmented las file at {las_segmented_path}')
        generate_segmented_las(las_path, chm_path, las_segmented_path)

        dbh_path = las_path.with_name(file.stem + '_dbh.csv')
        log.info(f'Generating dbh file at {dbh_path}')
        generate_diameter_at_base_height(las_segmented_path, chm_path,  dem_path, dbh_path)
