import rasterio
from fastlog import log

from pathlib import Path

import csv
import matplotlib.pyplot as plt

import numpy as np

import skimage



def generate_trunk_density(dbh_path, dem_path, td_path):
    
    # Load DBH
    with dbh_path.open() as file:
        reader = csv.DictReader(file)
        dbh_list = [row for row in reader]

    with rasterio.open(dem_path) as dem:
        dem_data = dem.read(1)
        transform = dem.transform
        crs = dem.crs
        driver = dem.driver

        # Find image scale
        pixel_size_x = abs(transform[0])
        pixel_size_y = abs(transform[4])
        pixel_size = sum([pixel_size_x, pixel_size_y]) / 2
        if pixel_size_x != pixel_size_y:
            log.warn('Target pixel shape is not square! This visualization may be inaccurate!')

        # Make output matrix in right shape
        tree_density_data = np.zeros( dem_data.shape )

        # For each tree...
        for dbh in dbh_list:

            # Compute area, add it to relevant pixels
            location = dem.index(dbh['X'], dbh['Y'])
            radius = float(dbh['DBH']) / 2

            # Scale radius by pixel size
            radius = radius / pixel_size

            # Create mask for this circle
            mask = create_circle_mask(radius, location, dem_data.shape)

            # Add this mask to the output image
            tree_density_data += mask


        # erase zeros
        tree_density_data[ tree_density_data==0 ] = np.nan

        # Display for debugging
        # plt.imshow(dem_data)
        # plt.imshow(tree_density_data)
        # plt.show()

    # Save output file
    with rasterio.open(
        td_path, 'w', driver=driver,
        height=dem_data.shape[0], width=dem_data.shape[1],
        count=1, dtype=dem_data.dtype,
        crs=crs, transform=transform,
    ) as tree_density:
        tree_density.write(tree_density_data, 1)            
        tree_density.close()

def create_circle_mask(radius, location, shape):
    target_area = np.pi * radius**2

    # create mask
    mask = np.zeros(shape).astype(float)
    disk_x, disk_y = skimage.draw.disk(location, radius, shape=shape)
    mask[disk_x, disk_y] = 1

    circle_rr, circle_cc, circle_val = remove_interior_anti_alias( *skimage.draw.circle_perimeter_aa(*location, int(radius), shape=shape) )


    # Superimpose
    mask[circle_rr, circle_cc] = circle_val
    first_pass_area = np.sum(mask)
    circle_area = np.sum(circle_val)

    # Scale circle by area
    # How much are we off by
    area_delta = (target_area - first_pass_area)
    circle_scale = (area_delta + circle_area) / circle_area

    circle_val = circle_val * circle_scale
    mask[circle_rr, circle_cc] = circle_val

    log.debug(f'target area: {target_area}')
    log.debug(f'rastered area: {np.sum(mask)}')

    return np.clip(mask, 0.0, 1.0)


def remove_interior_anti_alias(circle_rr, circle_cc, circle_val):

    # remove some duplicate rows
    circle_data = np.stack([circle_rr, circle_cc, circle_val], 1)
    circle_data = np.unique(circle_data, axis=0)
    # filter out zeros (why are they here?)
    circle_data = circle_data[ circle_data[:,2] != 0 ]


    # prepare for filter
    r_mean = np.mean(circle_data[:,0])
    c_mean = np.mean(circle_data[:,1])
    skip = np.zeros(len(circle_data))

    # Remove the inside of the circle
    for r in np.unique(circle_data[:,0]):
        
        mask = circle_data[:,0] == r

        data = circle_data[ mask ]
        cc = data[:,1]
        vals = data[:,2]
        
        peaks = cc[ vals == np.amax(vals) ]
        
        for c in cc:
            # in between the peak and center of circle
            skip[ np.logical_and(mask, circle_data[:,1] == c) ] = (np.any(peaks < c) and c <= c_mean) or (np.any(peaks > c) and c >= c_mean)


        # ----- Half-baked numpy version of the above loop
        # cc_thick = np.tile(cc, (len(peaks),1))
        # peaks_thick = np.tile(peaks, (len(cc),1)).T


        # cc_lt_peak = np.any(cc_thick < peaks_thick, axis=0)
        # cc_gt_peak = np.any(cc_thick > peaks_thick, axis=0)
        
        # cc_le_mean = cc <= c_mean
        # cc_ge_mean = cc >= c_mean

        # left_skip = np.logical_and(cc_gt_peak, cc_le_mean)
        # right_skip = np.logical_and(cc_lt_peak, cc_ge_mean)

        # # This indexing is broken  vvvv
        # skip[ np.logical_and(mask, circle_data[:,1] == cc) ] = np.logical_or( left_skip , right_skip )
    

    # Do skips
    circle_data = circle_data[ np.logical_not(skip) ]
    return circle_data[:,0].astype(int), circle_data[:,1].astype(int), circle_data[:,2]
    