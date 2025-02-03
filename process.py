import generate_dbh
import generate_trunk_density

import utils.argument_actions
import utils.geotiff_utils

from fastlog import log

import argparse
import subprocess
from pathlib import Path

import shutil
import rasterio



log_level_options = [log.WARNING, log.INFO, log.DEBUG]


def filter_outliers(pcd_path, las_path, crs):
    # filter outliers and generate las
    # TODO: make this faster jesus christ. This should be about 5 minutes
    return subprocess.call(['pdal', 'pipeline', 'outlier_rejection.json', '--progress=/dev/stdout',\
                            '--readers.pcd.filename', pcd_path,\
                            '--writers.las.filename', las_path,\
                            '--writers.las.a_srs', f'EPSG:{crs}'])

# def generate_las(pcd_path, las_path):
#     # Use pdal command to generate las. call blocks until command finishes.
#     return subprocess.call(['pdal', 'translate', pcd_path, las_path])

def split_inputs():
    # TODO: accept a pcd or las and split it into multiple tiled subcomponents
    pass

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

def generate_flammap_data(zip_in_path, zip_tmp_path, dem_path, flammap_path):
    # Get lat-long bounds with rasterio
    dem_bounds = utils.geotiff_utils.get_lat_long_bounds(dem_path)
    
    # Check that flammap data exists
    if not zip_in_path.exists():
        # TODO: If flammap data does not exist, pull it from appropriate source
        log.warning(f'Use Flammap to download data for these bounds: {dem_bounds}')
        quit()

    # Unzip
    shutil.unpack_archive(zip_in_path, zip_tmp_path)

    # Find flammap tif data (just grab the first file with a .tif extension)
    tif_path = next(zip_tmp_path.glob('*.tif'))

    # Move Flammap tif data to correct location
    shutil.move( str( tif_path ), str(flammap_path) )

def generate_merged_data(flammap_path, dem_path, chm_path, aspect_path, slope_path, merged_path):
    
    # Open input files
    with rasterio.open(flammap_path) as flammap_file, \
         rasterio.open(dem_path) as dem_file, \
         rasterio.open(chm_path) as chm_file, \
         rasterio.open(aspect_path) as aspect_file, \
         rasterio.open(slope_path) as slope_file:

        # Defining the goal:
        # I want to end up with one geotiff file
        # It should contain the layer descriptions from the flammap file
        # It should be in the CRS and shape of the smallest of our input files (we will just use the DEM file for now)
        # It should contain all of our input layers, and fill the rest with flammap data
        #       said flammap data must be rescaled to target CRS and shape

        target_crs = dem_file.crs
        target_shape = dem_file.shape
        target_transform = dem_file.transform

        # Descriptions
        # ('US_ELEV2020', 'US_SLPD2020', 'US_ASP2020', 'US_240FBFM40', 'US_240CC', 'US_240CH', 'US_240CBH', 'US_240CBD')
        desc_map = {
            'US_ELEV2020': dem_file,
            'US_240CBH': chm_file,
            'US_ASP2020': aspect_file,
            'US_SLPD2020': slope_file,
        }
        
        # Merge layers into output file
        with rasterio.open(merged_path, 'w', driver=flammap_file.driver,
                           height=target_shape[0], width=target_shape[1],
                           count=len(flammap_file.indexes),
                           dtype=dem_file.dtypes[0],
                           crs=target_crs, transform=target_transform) as merged_file:

            # For each layer
            for i, description in zip(flammap_file.indexes, flammap_file.descriptions):

                # If this is a layer that we generated, use that
                if description in desc_map.keys():
                    file = desc_map[description]
                    index = 1
                
                # Else, use the flammap data
                else:
                    file = flammap_file
                    index = i

                # Force use nearest-neighbor sampling for fuel model layer. Its important that we only use the existing values and not interpolate, because we later do lookups based on those values
                if description == 'US_240FBFM40':
                    resampling_method = rasterio.warp.Resampling.nearest
                else:
                    resampling_method = rasterio.warp.Resampling.bilinear


                # Downsample flammap data
                rasterio.warp.reproject(rasterio.band(file, index), rasterio.band(merged_file, i), resampling=resampling_method)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--input_location', action=utils.argument_actions.StorePathAction, default=Path('data/input'))
    parser.add_argument('--output_location', action=utils.argument_actions.StorePathAction, default=Path('data/output'))

    parser.add_argument('-v', action='count')
    parser.add_argument('--verbosity', type=int, default=1)

    parser.add_argument('--force-steps', type=int, default=0)
    
    args = parser.parse_args()

    # Process verbosity args
    verbosity = args.v if args.v else args.verbosity
    verbosity = min(verbosity, len(log_level_options)-1)
    log.setLevel(log_level_options[verbosity])

    tmp_folder_path = Path('data/tmp')


    # TODO: check dependencies
    # TODO: make threadpool for each input file

    for file in args.input_location.glob('**/*.pcd'):
        log.info(f'Processing input file {file}')
        with log.indent():

            pcd_path = file
            filename, crs = file.stem.rsplit('_', 1)

            step = 10

            output_directory = args.output_location / filename
            output_directory.mkdir(parents=True, exist_ok=True)

            las_path = (output_directory / filename).with_suffix('.las')
            zip_in_path =           file.with_suffix('.zip')
            # zip_tmp_path =          las_path.with_name(filename + '_flammap.tif')
            zip_tmp_path =          tmp_folder_path / filename

            dem_path =              las_path.with_name(filename + '_dem.tif')
            slope_path =            las_path.with_name(filename + '_slope.tif')
            aspect_path =           las_path.with_name(filename + '_aspect.tif')
            chm_path =              las_path.with_name(filename + '_chm.tif')
            las_segmented_path =    las_path.with_name(filename + '_segmented.las')
            dbh_path =              las_path.with_name(filename + '_dbh.csv')
            trunk_density_path =    las_path.with_name(filename + '_trunk_density.tif')
            flammap_path =          las_path.with_name(filename + '_flammap.tif')
            merged_path =           las_path.with_name(filename + '_merged.tif')


            step = step-1
            if step < args.force_steps:
                las_path.unlink(missing_ok=True)
            if las_path.exists():
                log.info(f'Skipping - Generate las file: already exists at {las_path}')
            else:
                log.info(f'Generating filtered las file at {las_path}. This will take some time...')
                filter_outliers(pcd_path, las_path, crs)


            step = step-1
            if step < args.force_steps:
                dem_path.unlink(missing_ok=True)
            if dem_path.exists():
                log.info(f'Skipping - Generate dem file: already exists at {dem_path}')
            else:
                log.info(f'Generating dem file at {dem_path}')
                generate_dem(las_path, dem_path)
            

            step = step-1
            if step < args.force_steps:
                slope_path.unlink(missing_ok=True)
            if slope_path.exists():
                log.info(f'Skipping - Generate slope file: already exists at {slope_path}')
            else:
                log.info(f'Generating slope file at {slope_path}')
                generate_slope(dem_path, slope_path)
            

            step = step-1
            if step < args.force_steps:
                aspect_path.unlink(missing_ok=True)
            if aspect_path.exists():
                log.info(f'Skipping - Generate aspect file: already exists at {aspect_path}')
            else:
                log.info(f'Generating aspect file at {aspect_path}')
                generate_aspect(dem_path, aspect_path)


            step = step-1
            if step < args.force_steps:
                chm_path.unlink(missing_ok=True)
            if chm_path.exists():
                log.info(f'Skipping - Generate chm file: already exists at {chm_path}')
            else:
                log.info(f'Generating chm file at {chm_path}')
                generate_base_canopy_height_model(las_path, chm_path)


            step = step-1
            if step < args.force_steps:
                las_segmented_path.unlink(missing_ok=True)
            if las_segmented_path.exists():
                log.info(f'Skipping - Generate segmented las file: already exists at {las_segmented_path}')
            else:
                log.info(f'Generating segmented las file at {las_segmented_path}')
                generate_segmented_las(las_path, chm_path, las_segmented_path)


            step = step-1
            if step < args.force_steps:
                dbh_path.unlink(missing_ok=True)
            if dbh_path.exists():
                log.info(f'Skipping - Generate dbh file: already exists at {dbh_path}')
            else:
                log.info(f'Generating dbh file at {dbh_path}')
                generate_diameter_at_base_height(las_segmented_path, chm_path,  dem_path, dbh_path)


            step = step-1
            if step < args.force_steps:
                trunk_density_path.unlink(missing_ok=True)
            if trunk_density_path.exists():
                log.info(f'Skipping - Generate density file: already exists at {trunk_density_path}')
            else:
                log.info(f'Generating trunk density file at {trunk_density_path}')
                generate_trunk_density_file(dbh_path, trunk_density_path)
            
            
            step = step-1
            if step < args.force_steps:
                flammap_path.unlink(missing_ok=True)
            if flammap_path.exists():
                log.info(f'Skipping - Generate flammap file: already exists at {flammap_path}')
            else:
                log.info(f'Generating flammap file at {flammap_path}')
                generate_flammap_data(zip_in_path, zip_tmp_path, dem_path, flammap_path)

            
            step = step-1
            if step < args.force_steps:
                merged_path.unlink(missing_ok=True)
            if merged_path.exists():
                log.info(f'Skipping - Generate merged file: already exists at {merged_path}')
            else:
                log.info(f'Generating merged file at {merged_path}')
                generate_merged_data(flammap_path, dem_path, chm_path, aspect_path, slope_path, merged_path)

            quit()
