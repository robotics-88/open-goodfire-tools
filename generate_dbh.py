import numpy as np
import laspy
from scipy.cluster.vq import kmeans2
import matplotlib.pyplot as plt

from fastlog import log
import warnings
import argparse

import utils.plotting
import utils.argument_actions

from pathlib import Path



# DBH is measured at 1.35m, for some reason
BREAST_HEIGHT = 1.35
SEARCH_REGION_HEIGHT = 1
# Config Parameters
# The feasible range of tree diameters
FEASIBLE_TREE_MIN = 0.1
FEASIBLE_TREE_MAX = 3
# The maximum number of trunks to look for
MAX_TRUNKS = 4


MIN_POINTS_FOR_ESTIMATE = 50
MAX_ESTIMATE_STANDARD_DEVIATION = 1.0


POINTS_WEIGHT = 0.01
DEVIATION_WEIGHT = 100

log_level_options = [log.WARNING, log.INFO, log.DEBUG]




def generate_dbh(las_file, csv_file):
    with laspy.open(las_file) as las_file_stream:
        las = las_file_stream.read()

    # Get all unique Tree ID's
    tree_ids = np.unique( las.points["treeID"] )

    dbh_list = []
    error_list = []

    # For each tree...
    for tree_id in tree_ids:
        # id 7,9,12,17,18,22,26,28,29,30,34,37,39,!48,!50 is well formed
        #                  ^
        # Get associated points
        tree_id = 22
        log.debug(f'Analyzing tree {tree_id}')

        with log.indent():
            tree = las.points[ las.points["treeID"] == tree_id ]


            # Normalize by ground level
            normalize_tree(tree)


            # TODO: handle errors and failures
            dbh, error = estimate_dbh_for_tree(tree)
            if dbh is None: continue
            
            print(dbh)
            dbh = dbh[0]

            
            dbh_list.append( dbh )
            fig = plt.figure()
            ax = fig.add_subplot(projection='3d')

            utils.plotting.plot_tree(ax, tree)
            utils.plotting.plot_circle(ax, *dbh)
            plt.show()

            quit()


    # TODO: log the total number of DBH's estimated, compare to total number of segmented trees
    # log.info(f'Generated {} diameter estimates from {len(tree_ids)} segmented trees')
    
    # TODO: log the total number of segmented trees that could not be processed and the adjacent reasons
    # log.info(f'Could not process {} segmented trees, for the following reasons:')
    # with log.indent():
    #     for reason in reasons:
    #         log.info(f'{reason} : {count}')

    # TODO: write to csv


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
        return num_points*POINTS_WEIGHT - sigma*DEVIATION_WEIGHT

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
        centroids, labels = kmeans2(tree_slice, k, minit='++')
    
    # Continue on empty cluster (no nead to repeat work done at k-1)
    if len(np.unique(labels)) < k:
        return None
    
    centroid_labels, centroid_point_count = np.unique(labels, return_counts=True)
    biggest_centroid = centroid_labels[ np.argmax(centroid_point_count) ]
    

    # 3. Iterate through clusters to get all trunks (even though there should only be one)
    for label in centroid_labels:
        cluster_points = tree_slice[ labels==label ]
        is_biggest_cluster = label == biggest_centroid


        # 4. Compute metrics
        # Flatten - Now that we have rejected other trees, we can operate in 2D
        cylinder_points = cluster_points[:,0:2]
        
        # Calculate center
        centroid = cylinder_points.mean(axis=0)
        
        # Calculate distance to center
        distances = np.linalg.norm( cylinder_points - centroid, axis=1 )

        # Calculate std_dev( distance to center )
        distance_deviation = np.std(distances)

        # Calcluate radius
        radius = np.mean(distances)

        if is_biggest_cluster:
            metrics_at_k = [ len(cluster_points), distance_deviation ]


        
        # 5. Validation checks
        #    - Are there enough points? Set an arbitrary threshold at 50
        #    - Is the standard deviation resonable?
        #    - Is the estimated size feasible?
        # If we find the largest cluster to be invalid, halt function, else continue looking at other clusters
        
        if len(cluster_points) < MIN_POINTS_FOR_ESTIMATE:
            log.debug(f'GUESS {label} REJECTED - INSUFFICIENT POINTS: {len(cluster_points)}')
            
            if is_biggest_cluster:
                log.debug(f'Failed to find estimate with {k} clusters')
                error_at_k = ('Insufficient points', len(cluster_points))
                break

            continue
        
        if distance_deviation > MAX_ESTIMATE_STANDARD_DEVIATION:
            log.debug(f'GUESS {label} REJECTED - EXCESSIVE DEVIATION: {distance_deviation}')
            
            if is_biggest_cluster:
                log.debug(f'Failed to find estimate with {k} clusters')
                error_at_k = ('Excessive deviation', distance_deviation)
                break

            continue

        if 2*radius < FEASIBLE_TREE_MIN:
            log.debug(f'GUESS {label} REJECTED - TOO SMALL TREE SIZE: {2*radius}')
            
            if is_biggest_cluster:
                log.debug(f'Failed to find estimate with {k} clusters')
                error_at_k = ('Estimate too small', 2*radius)
                break
            
            continue

        if 2*radius > FEASIBLE_TREE_MAX:
            log.debug(f'GUESS {label} REJECTED - TOO LARGE TREE SIZE: {2*radius}')
            
            if is_biggest_cluster:
                log.debug(f'Failed to find estimate with {k} clusters')
                error_at_k = ('Estimate too large', 2*radius)
                break
            
            continue

        
        # 6. Reject outliers by two-sigma
        filtered_cylinder_points = cylinder_points[ (distances-radius) < 2*distance_deviation ]

        # 7. Re-Generate circle from cluster location + average distance
        true_center = filtered_cylinder_points.mean(axis=0)
        true_distances = np.linalg.norm( filtered_cylinder_points - true_center, axis=1 )
        true_radius = np.mean(true_distances)

        guesses_at_k.append( (*true_center, 2*true_radius) )


    return guesses_at_k, error_at_k, metrics_at_k


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