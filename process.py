import argparse
from pathlib import Path
import subprocess


def split_inputs():
    # TODO: accept a pcd or las and split it into multiple tiled subcomponents
    pass

def generate_las(pcd_path, las_path):
    # Use pdal command to generate las. call blocks until command finishes.
    return subprocess.call(['pdal', 'translate', pcd_path, las_path])

def generate_dem(las_path, dem_path):
    # Use Rscript command to generate las.
    # Optionally, overwrite the existing dem with -o
    # TODO: restructure generate_dem.R to accept python style arguments
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

def generate_diameter_at_base_height(las_segmented_path, dbh_path):
    # TODO: write a script to consume segmented LAS data, and compute dbh. Start in R.
    pass



if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--input_location', default='data/input')
    parser.add_argument('--output_location', default='data/output')
    # parser.add_argument()
    # parser.add_argument()
    # parser.add_argument()

    args = parser.parse_args()
    args.input_location = Path(args.input_location)
    args.output_location = Path(args.output_location)

    for file in args.input_location.glob('**/*.pcd'):
        pcd_path = file

        output_directory = args.output_location / file.stem
        output_directory.mkdir(parents=True, exist_ok=True)


        las_path = (output_directory / file.stem).with_suffix('.las')
        print(f'Generating las file at {las_path}')
        # generate_las(pcd_path, las_path)
        
        dem_path = las_path.with_name(file.stem + '_dem.tif')
        print(f'Generating dem file at {dem_path}')
        generate_dem(las_path, dem_path)
        
        slope_path = las_path.with_name(file.stem + '_slope.tif')
        aspect_path = las_path.with_name(file.stem + '_aspect.tif')
        print(f'Generating slope file at {slope_path}')
        generate_slope(dem_path, slope_path)
        print(f'Generating aspect file at {aspect_path}')
        generate_aspect(dem_path, aspect_path)

        chm_path = las_path.with_name(file.stem + '_chm.tif')
        print(f'Generating chm file at {chm_path}')
        generate_base_canopy_height_model(las_path, chm_path)

        las_segmented_path = las_path.with_name(file.stem + '_segmented.las')
        print(f'Generating segmented las file at {las_segmented_path}')
        generate_segmented_las(las_path, chm_path, las_segmented_path)

        dbh_path = las_path.with_name(file.stem + '_dbh.csv')
        print(f'Generating dbh file at {dbh_path}')
        generate_diameter_at_base_height(las_segmented_path, dbh_path)
