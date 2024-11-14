import generate_dbh
import generate_trunk_density
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
    return generate_dbh.generate_dbh(las_segmented_path, chm_path,  dem_path, dbh_path)

def generate_trunk_density_file(dbh_path, td_path):
    return generate_trunk_density.generate_trunk_density(dbh_path, dem_path, td_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--input_location', action=utils.argument_actions.StorePathAction, default=Path('data/input'))
    parser.add_argument('--output_location', action=utils.argument_actions.StorePathAction, default=Path('data/output'))

    parser.add_argument('-v', action='count')
    parser.add_argument('--verbosity', type=int, default=1)

    parser.add_argument('--force-steps', type=int, default=1)
    
    args = parser.parse_args()

    # Process verbosity args
    verbosity = args.v if args.v else args.verbosity
    verbosity = min(verbosity, len(log_level_options)-1)
    log.setLevel(log_level_options[verbosity])

    # TODO: check dependencies

    for file in args.input_location.glob('**/*.pcd'):
        log.info(f'Processing input file {file}')
        with log.indent():

            pcd_path = file

            output_directory = args.output_location / file.stem
            output_directory.mkdir(parents=True, exist_ok=True)

            step = 8

            las_path = (output_directory / file.stem).with_suffix('.las')
            step = step-1
            if step < args.force_steps:
                las_path.unlink(missing_ok=True)
            if las_path.exists():
                log.info(f'Skipping - Generate las file: already exists at {las_path}')
            else:
                log.info(f'Generating las file at {las_path}')
                generate_las(pcd_path, las_path)
            

            dem_path = las_path.with_name(file.stem + '_dem.tif')
            step = step-1
            if step < args.force_steps:
                dem_path.unlink(missing_ok=True)
            if dem_path.exists():
                log.info(f'Skipping - Generate dem file: already exists at {dem_path}')
            else:
                log.info(f'Generating dem file at {dem_path}')
                generate_dem(las_path, dem_path)
            

            slope_path = las_path.with_name(file.stem + '_slope.tif')
            step = step-1
            if step < args.force_steps:
                slope_path.unlink(missing_ok=True)
            if slope_path.exists():
                log.info(f'Skipping - Generate slope file: already exists at {slope_path}')
            else:
                log.info(f'Generating slope file at {slope_path}')
                generate_slope(dem_path, slope_path)
            

            aspect_path = las_path.with_name(file.stem + '_aspect.tif')
            step = step-1
            if step < args.force_steps:
                aspect_path.unlink(missing_ok=True)
            if aspect_path.exists():
                log.info(f'Skipping - Generate aspect file: already exists at {aspect_path}')
            else:
                log.info(f'Generating aspect file at {aspect_path}')
                generate_aspect(dem_path, aspect_path)


            chm_path = las_path.with_name(file.stem + '_chm.tif')
            step = step-1
            if step < args.force_steps:
                chm_path.unlink(missing_ok=True)
            if chm_path.exists():
                log.info(f'Skipping - Generate chm file: already exists at {chm_path}')
            else:
                log.info(f'Generating chm file at {chm_path}')
                generate_base_canopy_height_model(las_path, chm_path)


            las_segmented_path = las_path.with_name(file.stem + '_segmented.las')
            step = step-1
            if step < args.force_steps:
                las_segmented_path.unlink(missing_ok=True)
            if las_segmented_path.exists():
                log.info(f'Skipping - Generate segmented las file: already exists at {las_segmented_path}')
            else:
                log.info(f'Generating segmented las file at {las_segmented_path}')
                generate_segmented_las(las_path, chm_path, las_segmented_path)


            dbh_path = las_path.with_name(file.stem + '_dbh.csv')
            step = step-1
            if step < args.force_steps:
                dbh_path.unlink(missing_ok=True)
            if dbh_path.exists():
                log.info(f'Skipping - Generate dbh file: already exists at {dbh_path}')
            else:
                log.info(f'Generating dbh file at {dbh_path}')
                generate_diameter_at_base_height(las_segmented_path, chm_path,  dem_path, dbh_path)


            trunk_density_path = las_path.with_name(file.stem + '_trunk_density.tif')
            step = step-1
            if step < args.force_steps:
                trunk_density_path.unlink(missing_ok=True)
            if trunk_density_path.exists():
                log.info(f'Skipping - Generate density file: already exists at {trunk_density_path}')
            else:
                log.info(f'Generating trunk density file at {trunk_density_path}')
                generate_trunk_density_file(dbh_path, trunk_density_path)
