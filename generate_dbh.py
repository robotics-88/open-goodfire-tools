import numpy as np
from scipy.cluster.vq import kmeans2
import scipy
import laspy
from fastlog import log
import matplotlib.pyplot as plt
import os
import sys

import warnings

import scipy.special


# DBH is measured at 1.35m, for some reason
BREAST_HEIGHT = 1.35
dbh_slice_width = 1
# Config Parameters
# The feasible range of tree diameters
feasible_range = [0.1, 3]
# The maximum number of trunks to look for
num_trunks = 4




def generate_dbh(las_file):
    with laspy.open(las_file) as las_file_stream:
        las = las_file_stream.read()

    # Get all unique Tree ID's
    tree_ids = np.unique( las.points["treeID"] )

    dbh_list = []

    # For each tree...
    for tree_id in tree_ids:
        # id 7,9,12,17,18,22,26,28,29,30,34,37,39,!48,!50 is well formed
        #                  ^
        # Get associated points
        # tree_id = 22
        tree = las.points[ las.points["treeID"] == tree_id ]


        # Normalize by ground level
        normalize_tree(tree)


        # TODO: handle errors and failures
        dbh = estimate_dbh_for_tree(tree)
        if dbh is None: continue



        dbh_list.append( dbh )

        ax, fig = plot_tree(tree)
        plot_circle(ax, *dbh[0:3])

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
    
    
    tree = np.array([tree['x'], tree['y'], tree['z']])
    
    slice_top = BREAST_HEIGHT + dbh_slice_width/2
    slice_bottom = BREAST_HEIGHT - dbh_slice_width/2
    mask = np.vectorize(lambda z: slice_bottom < z and z < slice_top)(tree[2])

    # Transpose and filter. TODO: Transpose earlier for clarity
    tree_slice = tree.T[mask]


    # Output list of guesses to compare
    # 4 guesses with 6 properties
    guesses = []
    errors = []

    if len(tree_slice) == 0:
        return None

    # 1. For k in 1..4
    for k in range(1,1+num_trunks):

        # 2. Segment into k clusters - to reject other trees as best we can, we will run clustering in 3D
        # Suppress scipy warnings (why is this so hard!!)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            centroids, labels = kmeans2(tree_slice, k, minit='++')
        
        # Continue on empty cluster (no nead to repeat work done at k-1)
        if len(np.unique(labels)) < k:
            continue
        
        # 3. Take the biggest cluster
        centroid_labels, centroid_point_count = np.unique(labels, return_counts=True)
        biggest_centroid = centroid_labels[ np.argmax(centroid_point_count) ]
        
        cluster_points = tree_slice[ labels==biggest_centroid ]
        


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


        
        # 5. Validation checks
        #    - Are there enough points? Set an arbitrary threshold at 50
        #    - Is the standard deviation resonable?
        
        # TODO: these are arbitrary thresholds. parametrize
        if len(cluster_points) < 50:
            print(f'GUESS {k} REJECTED - INSUFFICIENT POINTS: {len(cluster_points)}')
            errors.append(['Insufficient points', len(cluster_points), len(cluster_points), distance_deviation])
            continue
        
        if distance_deviation >= 1:
            print(f'GUESS {k} REJECTED - EXCESSIVE DEVIATION: {distance_deviation}')
            errors.append(['Excessive deviation', distance_deviation, len(cluster_points), distance_deviation])
            continue

        # Check for feasible radius
        if min(feasible_range) > 2*radius or 2*radius > max(feasible_range):
            print(f'GUESS {k} REJECTED - INFEASIBLE TREE SIZE: {2*radius}')
            errors.append(['Infeasible tree size', 2*radius, len(cluster_points), distance_deviation])
            continue



        # 6. Reject outliers by two-sigma
        filtered_cylinder_points = cylinder_points[ (distances-radius) < 2*distance_deviation ]

        # 7. Re-Generate circle from cluster location + average distance
        true_center = filtered_cylinder_points.mean(axis=0)
        true_distances = np.linalg.norm( filtered_cylinder_points - true_center, axis=1 )
        true_radius = np.mean(true_distances)



        guesses.append( [ *true_center, 2*true_radius, len(cluster_points), distance_deviation] )

    
    # 8. Rank guesses. Score by
    #    - num points in cluster
    #    - sandard deviation in distance from cluster

    # If no valid guesses were generated
    # TODO: get error reasons instead
    if len(guesses) == 0: return None

    # Make and calculate an arbitrary scoring function - TODO: parametrize
    guesses = np.array(guesses)
    scores = guesses[:,3]*0.01 - guesses[:,4]*100
    # print(f'Selecting guess {np.argmax(scores)}')
    # Find winner
    return guesses[ np.argmax(scores) , 0:3 ]


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
    scipy.special.seterr(all='ignore')
    generate_dbh('data/output/illinois_utm/illinois_utm_segmented.las')