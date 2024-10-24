import numpy as np
import laspy
from scipy.cluster.vq import kmeans2

# from typing import Optional, Tuple, List

from fastlog import log
import warnings
import matplotlib.pyplot as plt




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




def generate_dbh(las_file):
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

            ax, fig = plot_tree(tree)
            plot_circle(ax, *dbh)


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
                continue
            
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
                # If we find the largest cluster to be invalid, halt this loop of k, else continue looking at other clusters
                
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


        # Did we find any valid guesses for this value of k?
        if len(guesses_at_k) != 0:
            guesses.append( [guesses_at_k, *metrics_at_k] )
        else:
            errors.append( [error_at_k, *metrics_at_k] )

    
    # 8. Rank guesses. Score by
    #    - num points in cluster
    #    - sandard deviation in distance from cluster

    # TODO: parametrize
    def score_function(num_points, sigma):
        return num_points*0.01 - sigma*100

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
        scores = [ score_function(error[1], error[2]) for error in errors ]

        # Find + return winner
        log.debug(f'Returning set { np.argmax(scores) }')
        return None, errors[ np.argmax(scores) ][0]


def plot_circle(ax, x, y, d):
    r = d/2

    theta = np.linspace(0, 2*np.pi, 201)
    xs = np.sin(theta)
    ys = np.cos(theta)

    ax.scatter(r*xs + x, r*ys + y, [1.35]*201)
    ax.scatter(2*xs + x, 2*ys + y, [1.35]*201)
    plt.show()

def plot_tree(tree):
    plot_point_no = 10000
    plot_subset_ratio = plot_point_no / len(tree)
    
    plot_subset_mask = np.random.uniform(size=len(tree)) < plot_subset_ratio
    
    plot_subset = tree[ plot_subset_mask ]

    fig = plt.figure()
    ax = fig.add_subplot(projection='3d')
    ax.scatter(plot_subset['x'], plot_subset['y'], plot_subset['z'])

    ax.set_xlabel('X Label')
    ax.set_ylabel('Y Label')
    ax.set_zlabel('Z Label')

    ax.set_aspect('equal', adjustable='box')
    # plt.show()

    return ax, fig

def plot_np(tree):
    plot_point_no = 10000
    plot_subset_ratio = plot_point_no / len(tree)
    
    plot_subset_mask = np.random.uniform(size=len(tree)) < plot_subset_ratio
    
    plot_subset = tree[ plot_subset_mask ]

    fig = plt.figure()
    ax = fig.add_subplot(projection='3d')
    ax.scatter(plot_subset[:,0], plot_subset[:,1], plot_subset[:,2])

    ax.set_xlabel('X Label')
    ax.set_ylabel('Y Label')
    ax.set_zlabel('Z Label')

    ax.set_aspect('equal', adjustable='box')
    # plt.show()

    return ax, fig


if __name__ == '__main__':
    # generate_dbh('data/output/smaller/smaller_segmented.las')
    # scipy.special.seterr(all='ignore')
    log.setLevel(log.DEBUG)
    generate_dbh('data/output/illinois_utm/illinois_utm_segmented.las')