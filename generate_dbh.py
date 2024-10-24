import utils.argument_actions
import utils.plotting

import laspy
import matplotlib.pyplot as plt
import numpy as np
from fastlog import log
from scipy.cluster.vq import kmeans2

import argparse
import csv
import warnings
from pathlib import Path





# Config Parameters

# DBH is measured at 1.35m, for some reason
BREAST_HEIGHT = 1.35
SEARCH_REGION_HEIGHT = 1
# The feasible range of tree diameters
FEASIBLE_TREE_MIN = 0.1
FEASIBLE_TREE_MAX = 3
# The maximum number of trunks to look for
MAX_TRUNKS = 4
# How many points we require to compute an estimate
MIN_POINTS_FOR_ESTIMATE = 50
# Maximum standard deviation in meters (this should probably be smaller)
MAX_ESTIMATE_STANDARD_DEVIATION = 1.0
# How much weight to give number of points in the scoring function
POINTS_WEIGHT = 0.01
# How much weight to give standard deviation in the scoring function
DEVIATION_WEIGHT = -100

log_level_options = [log.WARNING, log.INFO, log.DEBUG]




def generate_dbh(las_file, csv_file):
    log.info(f'Loading .las file from {las_file}')
    with laspy.open(las_file) as las_file_stream:
        las = las_file_stream.read()

    # Get all unique Tree ID's
    tree_ids = np.unique( las.points["treeID"] )

    dbh_list = []
    error_list = []

    # For each tree...
    log.info('Computing DBH...')
    for tree_id in tree_ids:
        
        log.debug(f'Analyzing tree {int(tree_id)}')

        with log.indent():
            tree = las.points[ las.points["treeID"] == tree_id ]

            # Normalize by ground level
            normalize_tree(tree)

            dbh_estimates, error = estimate_dbh_for_tree(tree)

            # Function may return None if it does no work
            if dbh_estimates is None:
                error_list.append(error)
                continue
                
            # Else, store result
            dbh_list.extend( dbh_estimates )

            # Optionally plot each resultant estimate
            if VISUALIZE_FLAG:
                fig = plt.figure()
                ax = fig.add_subplot(projection='3d')

                utils.plotting.plot_tree(ax, tree)
                for dbh in dbh_estimates:
                    utils.plotting.plot_circle(ax, *dbh)
                    utils.plotting.plot_circle(ax, *dbh[0:2], 3)
                plt.show()

    # Discard large LAS object from memory
    las = None

    # log the total number of estimates generated
    log.success(f'Generated {len(dbh_list)} diameter estimates from a total of {len(tree_ids)} segmented trees')
    
    # log the total number of segmented trees that could not be processed and the adjacent reasons
    log.info(f'Could not process {len(error_list)} segmented trees, for the following reasons:')
    with log.indent():
        error_list_np = np.array(error_list)
        reasons, counts = np.unique( error_list_np[:,0], return_counts=True )
        for reason, count in zip(reasons, counts):
            log.info(f'{reason} : {count}')

    # TODO: Load CHM
    chm = None
    heights = get_canopy_height_at_locations(dbh_list, chm)
    
    # Discard large CHM object from memory
    chm = None

    # Write to csv
    with csv_file.open('w') as csv_file_stream:
        writer = csv.writer(csv_file_stream)
        writer.writerow(['X', 'Y', 'DBH', 'Height'])
        for dbh, height in zip(dbh_list, heights):
            # placeholder height
            writer.writerow([*dbh, height])

def normalize_tree(tree):
    tree['z'] = tree['z'] - min(tree['z'])

def estimate_dbh_for_tree(tree):
    '''
    Here's the plan:
    0. Filter for data in the vague region of chest height
    1. Assume that we have captured k = 1..4 trees trunks in the segmented data
    2. Segment the data into k clusters
    3. Take the biggest cluster
    4. Validation checks
        - Are there enough points? Set an arbitrary threshold at 50
        - Is the standard deviation reasonable?
    5. Reject outliers
    6. Generate circle from cluster location + average distance
    7. Rank guesses. Score by
        - num points in cluster
        - sandard deviation in distance from cluster

    '''    

            # 0. Look at only the "chest high" section of the data 
        # Convert to np array
    
    # convert to np array
    tree = np.array([tree['x'], tree['y'], tree['z']])
    
    # slice
    slice_top = BREAST_HEIGHT + SEARCH_REGION_HEIGHT/2
    slice_bottom = BREAST_HEIGHT - SEARCH_REGION_HEIGHT/2
    mask = np.vectorize(lambda z: slice_bottom < z and z < slice_top)(tree[2])

    # Transpose and filter. TODO: Transpose earlier for clarity
    tree_slice = tree.T[mask]


    # Catch empty point cloud
    if len(tree_slice) == 0:
        return None, ('No points at chest height', 0)
    

    # Prepare output list of guesses, errors to compare
    guesses = []
    errors = []

    # 1. For k in 1..MAX_TRUNKS
    for k in range(1,1+MAX_TRUNKS):

        log.debug(f'Trying {k} clusters')
        with log.indent():
            result = estimate_dbh_for_tree_with_clusters(tree_slice, k)
        
        # function may return None if it did no work. else, unpack
        if not result:
            continue
        guesses_at_k, error_at_k, metrics_at_k = result

        # Did we find any valid guesses for this value of k?
        if len(guesses_at_k) != 0:
            guesses.append( [guesses_at_k, *metrics_at_k] )
        else:
            errors.append( [error_at_k, *metrics_at_k] )

    
    # 8. Rank guesses by
    #    - num points in cluster
    #    - sandard deviation in distance from cluster

    def score_function(num_points, sigma):
        return num_points*POINTS_WEIGHT + sigma*DEVIATION_WEIGHT

    # If valid guesses were generated
    if len(guesses) != 0:
        log.debug(f'Comparing {len(guesses)} sets of guesses')

        # Calculate scoring function
        scores = [ score_function(guess[1], guess[2]) for guess in guesses ]
        
        # Find + return winner
        log.debug(f'Returning set { np.argmax(scores) }')
        return guesses[ np.argmax(scores) ][0], None
    
    # No valid guesses were generated
    else:
        log.debug(f'Failed to produce any valid guess. Comparing {len(errors)} sets of errors:')
        
        # Calculate scoring function
        scores = [ score_function(error[1], error[2]) for error in errors ]

        # Find + return winner
        log.debug(f'Returning set { np.argmax(scores) }')
        return None, errors[ np.argmax(scores) ][0]

def estimate_dbh_for_tree_with_clusters(tree_slice, k):
    guesses_at_k = []
    error_at_k = None
    metrics_at_k = None

    # 2. Segment into k clusters - to reject other trees as best we can, we will run clustering in 3D
    # Suppress scipy warnings (why is this so hard!!)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, point_labels = kmeans2(tree_slice, k, minit='++')
    
    # Continue on empty cluster (no nead to repeat work done at k-1)
    if len(np.unique(point_labels)) < k:
        return None
    
    cluster_labels, cluster_point_count = np.unique(point_labels, return_counts=True)
    biggest_cluster_label = cluster_labels[ np.argmax(cluster_point_count) ]
    

    # 3. Iterate through clusters to get all trunks (even though there should only be one)
    for cluster_label in cluster_labels:
        points_in_cluster = tree_slice[ point_labels==cluster_label ]
        is_biggest_cluster = cluster_label == biggest_cluster_label


        # 4. Compute metrics
        # Flatten - Now that we have rejected other trees, we can operate in 2D
        points_in_cluster_2d = points_in_cluster[:,0:2]
        
        # Calculate center
        centroid_2d = points_in_cluster_2d.mean(axis=0)
        
        # Calculate distance to center
        point_distances_from_centroid = np.linalg.norm( points_in_cluster_2d - centroid_2d, axis=1 )

        # Calculate std_dev( distance to center )
        standard_deviation = np.std(point_distances_from_centroid)

        # Calcluate radius
        diameter = 2*np.mean(point_distances_from_centroid)

        if is_biggest_cluster:
            metrics_at_k = [ len(points_in_cluster), standard_deviation ]


        
        # 5. Validation checks
        #    - Are there enough points? Set an arbitrary threshold at 50
        #    - Is the standard deviation resonable?
        #    - Is the estimated size feasible?
        # If we find the largest cluster to be invalid, halt function, else continue looking at other clusters
        
        if len(points_in_cluster) < MIN_POINTS_FOR_ESTIMATE:
            log.debug(f'GUESS {cluster_label} REJECTED - INSUFFICIENT POINTS: {len(points_in_cluster)}')
            
            if is_biggest_cluster:
                log.debug(f'Failed to find estimate with {k} clusters')
                error_at_k = ('Insufficient points', len(points_in_cluster))
                break

            continue
        
        if standard_deviation > MAX_ESTIMATE_STANDARD_DEVIATION:
            log.debug(f'GUESS {cluster_label} REJECTED - EXCESSIVE DEVIATION: {standard_deviation}')
            
            if is_biggest_cluster:
                log.debug(f'Failed to find estimate with {k} clusters')
                error_at_k = ('Excessive deviation', standard_deviation)
                break

            continue

        if diameter < FEASIBLE_TREE_MIN:
            log.debug(f'GUESS {cluster_label} REJECTED - TOO SMALL TREE SIZE: {diameter}')
            
            if is_biggest_cluster:
                log.debug(f'Failed to find estimate with {k} clusters')
                error_at_k = ('Estimate too small', diameter)
                break
            
            continue

        if diameter > FEASIBLE_TREE_MAX:
            log.debug(f'GUESS {cluster_label} REJECTED - TOO LARGE TREE SIZE: {diameter}')
            
            if is_biggest_cluster:
                log.debug(f'Failed to find estimate with {k} clusters')
                error_at_k = ('Estimate too large', diameter)
                break
            
            continue

        
        # 6. Reject outliers by two-sigma
        points_in_cluster_2d_filtered = points_in_cluster_2d[ (point_distances_from_centroid - (diameter/2)) < 2*standard_deviation ]

        # 7. Re-Generate circle from cluster location + average distance
        final_centroid_2d = points_in_cluster_2d_filtered.mean(axis=0)
        final_point_distances = np.linalg.norm( points_in_cluster_2d_filtered - final_centroid_2d, axis=1 )
        final_diameter = 2*np.mean(final_point_distances)

        guesses_at_k.append( (*final_centroid_2d, final_diameter) )


    return guesses_at_k, error_at_k, metrics_at_k

def get_canopy_height_at_locations(dhm_list, chm):
    # TODO: figure out how to process chm files
    dhm_list_np = np.array(dhm_list)

    return [1]*len(dhm_list)



if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('-v', action='count')
    parser.add_argument('--verbosity', type=int, default=0)
    parser.add_argument('--visualize', action='store_true')

    parser.add_argument('--input_path', action=utils.argument_actions.StorePathAction, default=Path('data/output/illinois_utm/illinois_utm_segmented.las'))
    parser.add_argument('--output_path', action=utils.argument_actions.StorePathAction, default=None)

    args = parser.parse_args()

    # Process verbosity args
    verbosity = args.v if args.v else args.verbosity
    verbosity = min(verbosity, len(log_level_options)-1)
    log.setLevel(log_level_options[verbosity])

    # Process visualizer args
    VISUALIZE_FLAG = args.visualize

    # Process path args
    if not args.output_path:
        args.output_path = Path(args.input_path.with_suffix('.csv'))


    generate_dbh(args.input_path, args.output_path)