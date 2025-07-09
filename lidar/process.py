
from scripts import download_landfire
from scripts import generate_dbh
from scripts import generate_fuelvolume
from scripts import generate_trunk_density
from scripts import register_laz

import utils.geotiff_utils

from fastlog import log

import argparse
import subprocess
from pathlib import Path

import shutil
import rasterio
import json


log_level_options = [log.WARNING, log.INFO, log.DEBUG]


def filter_outliers(las_path, filtered_path):
    pipeline_json = [
        {
            "type": "readers.las",
            "filename": str(las_path)
        },
        {
            "type": "filters.outlier",
            "method": "statistical",
            "mean_k": 8,
            "multiplier": 2.5
        },
        {
            "type": "filters.range",
            "limits": "Classification![7:7]"
        },
        {
            "type": "writers.las",
            "filename": str(filtered_path),
            "compression": "laszip"
        }
    ]
    result = subprocess.run(
        ["pdal", "pipeline", "--stdin"],
        input=json.dumps(pipeline_json).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    if result.returncode == 0:
        print("✅ PDAL pipeline executed successfully")
        print(result.stdout.decode("utf-8"))
    else:
        print("❌ PDAL pipeline failed")
        print(result.stderr.decode("utf-8"))

def split_inputs():
    # TODO: accept a pcd or las and split it into multiple tiled subcomponents
    pass

    
def generate_slope(dem_path, slope_path):
    # Use gdal command to generate slope. call blocks until command finishes.
    return subprocess.call(['gdaldem', 'slope', dem_path, slope_path])

def generate_aspect(dem_path, aspect_path):
    # Use gdal command to generate aspect. call blocks until command finishes.
    return subprocess.call(['gdaldem', 'aspect', dem_path, aspect_path])

def generate_segmented_las(las_path, chm_path, las_segmented_path):
    return subprocess.call(['./scripts/segment_las.R', las_path, chm_path, las_segmented_path])

def generate_diameter_at_base_height(las_segmented_path, chm_path,  dem_path, dbh_path):
    return generate_dbh.generate_dbh(las_segmented_path, chm_path,  dem_path, dbh_path)

def generate_trunk_density_file(dbh_path, td_path):
    return generate_trunk_density.generate_trunk_density(dbh_path, dem_path, td_path)

def generate_flammap_data(landfire_path, dem_path, flammap_path):
    # Get lat-long bounds with rasterio
    dem_bounds = utils.geotiff_utils.get_lat_long_bounds(dem_path, flammap_crs)
    dem_str = ' '.join(map(str, dem_bounds))
    
    # Check that flammap data exists
    if not landfire_path.exists():
        log.warning(f'Using LANDFIRE to download data for these bounds: {dem_str}')
        try:
            download_landfire.download_flammap_data(flammap_crs, dem_str, output_path)
            shutil.unpack_archive(landfire_path, extract_dir=flammap_path)
        except Exception as e:
            log.warning(f'❌ Failed to download LANDFIRE data: {e}')
            return None

    # Find flammap tif data
    try:
        tif_path = next(flammap_path.glob('*.tif'))
        return tif_path
    except StopIteration:
        log.warning('⚠️ No .tif file found in flammap path.')
        return None


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

    parser.add_argument('dataset', help='Name of the dataset (e.g., mydataset)')
    dataset = parser.parse_args().dataset
    dataset = dataset.replace(' ', '_')
    input_path = Path('data') / dataset / 'input/before'
    output_path = Path('data') / dataset / 'output'

    if not input_path.exists():
        parser.error(f"Input folder does not exist: {input_path}")
        quit()

    do_after = True
    after_path = input_path.parent / 'after'
    print(f"Checking for 'after' folder at {after_path}")
    if not after_path.exists():
        parser.error(f"'after' folder does not exist: {after_path}. Proceeding without it.")
        do_after = False

    parser.add_argument('-v', action='count')
    parser.add_argument('--verbosity', type=int, default=1)
    
    args = parser.parse_args()

    # Process verbosity args
    verbosity = args.v if args.v else args.verbosity
    verbosity = min(verbosity, len(log_level_options)-1)
    log.setLevel(log_level_options[verbosity])

    tmp_folder_path = Path('data/tmp')

    flammap_crs = 4326

    # TODO: check dependencies
    # TODO: make threadpool for each input file

    for file in input_path.glob('**/*.laz'):
        log.info(f'Processing input file {file}')
        with log.indent():

            laz_path = file

            step = 10

            output_path.mkdir(parents=True, exist_ok=True)

            filtered_las_path = output_path / (dataset + '_filtered.laz')

            dem_path =              output_path / (dataset + '_dem.tif')
            slope_path =            output_path / (dataset + '_slope.tif')
            aspect_path =           output_path / (dataset + '_aspect.tif')
            chm_path =              output_path / (dataset + '_chm.tif')
            las_segmented_path =    output_path / (dataset + '_segmented.laz')
            dbh_path =              output_path / (dataset + '_dbh.csv')
            trunk_density_path =    output_path / (dataset + '_trunk_density.tif')
            landfire_path =         output_path / 'landfire_data.zip'
            flammap_path =          output_path / 'landfire_data'
            merged_path =           output_path / (dataset + '_merged.tif')
            fuel_volume_path =      output_path / (dataset + '_fuel_volume.tif')


            if filtered_las_path.exists():
                log.info(f'Skipping - Generate las file: already exists at {filtered_las_path}')
            else:
                log.info(f'Generating filtered las file at {filtered_las_path}. This will take some time...')
                filter_outliers(laz_path, filtered_las_path)


            if dem_path.exists() and chm_path.exists():
                log.info(f'Skipping - Generate dem and chm file: both already exists at {dem_path} and {chm_path}')
            else:
                log.info(f'Generating dem and chm file at {dem_path} and {chm_path}.')
                subprocess.call(['./scripts/generate_dem.R', filtered_las_path, dem_path, chm_path, las_segmented_path])


            if slope_path.exists():
                log.info(f'Skipping - Generate slope file: already exists at {slope_path}')
            else:
                log.info(f'Generating slope file at {slope_path}')
                generate_slope(dem_path, slope_path)


            if aspect_path.exists():
                log.info(f'Skipping - Generate aspect file: already exists at {aspect_path}')
            else:
                log.info(f'Generating aspect file at {aspect_path}')
                generate_aspect(dem_path, aspect_path)


            if las_segmented_path.exists():
                log.info(f'Skipping - Generate segmented las file: already exists at {las_segmented_path}')
            else:
                log.info(f'Generating segmented las file at {las_segmented_path}')
                generate_segmented_las(filtered_las_path, chm_path, las_segmented_path)


            if dbh_path.exists():
                log.info(f'Skipping - Generate dbh file: already exists at {dbh_path}')
            else:
                log.info(f'Generating dbh file at {dbh_path}')
                generate_diameter_at_base_height(las_segmented_path, chm_path,  dem_path, dbh_path)


            if trunk_density_path.exists():
                log.info(f'Skipping - Generate density file: already exists at {trunk_density_path}')
            else:
                log.info(f'Generating trunk density file at {trunk_density_path}')
                generate_trunk_density_file(dbh_path, trunk_density_path)
            

            if landfire_path.exists():
                log.info(f'Skipping - Generate landfire file: already exists at {landfire_path}')
            else:
                log.info(f'Generating landfire file at {landfire_path}')
                flammap_path = generate_flammap_data(landfire_path, dem_path, flammap_path)


            if merged_path.exists():
                # If we already have a merged file, we can skip this step
                # But we still need to check if the flammap_path exists, because if not, LANDFIRE failed to download
                log.info(f'Skipping - Generate merged file: already exists at {merged_path}')
            elif flammap_path is not None:
                log.info(f'Generating merged file at {merged_path}')
                generate_merged_data(flammap_path, dem_path, chm_path, aspect_path, slope_path, merged_path)
            else:
                log.warning(f'❌ Failed to generate merged file at {merged_path} because flammap data was not downloaded successfully. Please check the LANDFIRE download step.')


            if do_after:
                after_laz_path = after_path / 'after.laz'
                if not after_laz_path.exists():
                    log.warning(f'❌ After file does not exist: {after_laz_path}. Skipping fuel volume step.')
                else:
                    filtered_after_laz_path = after_path / 'after_filtered.laz'
                    if filtered_after_laz_path.exists():
                        log.info(f'Skipping - Generate filtered after.laz file: already exists at {filtered_after_laz_path}')
                    else:
                        log.info(f'Generating filtered after.laz file at {filtered_after_laz_path}')
                        filter_outliers(after_laz_path, filtered_after_laz_path)
                    log.info(f'Registering {filtered_las_path} with {filtered_after_laz_path}')
                    adjusted_laz_path = after_path / 'after-adjusted.laz'
                    if adjusted_laz_path.exists():
                        log.info(f'Skipping - Adjusted point cloud already exists at {adjusted_laz_path}')
                    else:
                        register_laz.register_laz(filtered_las_path, filtered_after_laz_path)
                        log.info(f'✅ Successfully registered and saved adjusted point cloud to: {adjusted_laz_path}')

                    if adjusted_laz_path.exists():
                        generate_fuelvolume.compute_fuel_volume(filtered_las_path, adjusted_laz_path, output_path, resolution=1.0)
                        log.info(f'✅ Successfully generated fuel volume data and saved to: {fuel_volume_path}')
                    else:
                        log.error(f'❌ Failed to save adjusted point cloud to: {adjusted_laz_path}. Please check the registration step.')

            quit()
