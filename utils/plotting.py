import numpy as np
import matplotlib.pyplot as plt


def plot_circle(ax, x, y, d):
    r = d/2

    theta = np.linspace(0, 2*np.pi, 201)
    xs = np.sin(theta)
    ys = np.cos(theta)

    ax.scatter(r*xs + x, r*ys + y, [1.35]*201)
    ax.scatter(2*xs + x, 2*ys + y, [1.35]*201)
    

def plot_tree(ax, tree):
    plot_point_no = 10000
    plot_subset_ratio = plot_point_no / len(tree)
    
    plot_subset_mask = np.random.uniform(size=len(tree)) < plot_subset_ratio
    
    plot_subset = tree[ plot_subset_mask ]

    
    ax.scatter(plot_subset['x'], plot_subset['y'], plot_subset['z'])

    ax.set_xlabel('X Label')
    ax.set_ylabel('Y Label')
    ax.set_zlabel('Z Label')

    ax.set_aspect('equal', adjustable='box')


def plot_np(ax, tree):
    plot_point_no = 10000
    plot_subset_ratio = plot_point_no / len(tree)
    
    plot_subset_mask = np.random.uniform(size=len(tree)) < plot_subset_ratio
    
    plot_subset = tree[ plot_subset_mask ]

    ax.scatter(plot_subset[:,0], plot_subset[:,1], plot_subset[:,2])

    ax.set_xlabel('X Label')
    ax.set_ylabel('Y Label')
    ax.set_zlabel('Z Label')

    ax.set_aspect('equal', adjustable='box')