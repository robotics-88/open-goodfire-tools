import open3d as o3d
import laspy
import numpy as np
import os
from pathlib import Path

def load_laz_as_pcd(path):
    las = laspy.read(path)
    points = np.vstack((las.x, las.y, las.z)).T
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    return pcd, las

def save_pcd_as_laz(pcd, crs, output_path):
    points = np.asarray(pcd.points)
    header = laspy.LasHeader(point_format=3, version="1.2")
    header.add_crs(crs)
    header.offsets = np.min(points, axis=0)
    header.scales = np.array([0.001, 0.001, 0.001])  # or appropriate scale

    new_las = laspy.LasData(header)
    new_las.x, new_las.y, new_las.z = points[:, 0], points[:, 1], points[:, 2]

    new_las.write(output_path)

def preprocess(pcd, voxel_size):
    pcd_down = pcd.voxel_down_sample(voxel_size)
    pcd_down.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel_size*2, max_nn=30))
    fpfh = o3d.pipelines.registration.compute_fpfh_feature(
        pcd_down,
        o3d.geometry.KDTreeSearchParamHybrid(radius=voxel_size*5, max_nn=100)
    )
    return pcd_down, fpfh

def global_align(src, tgt, src_fpfh, tgt_fpfh, voxel_size):
    return o3d.pipelines.registration.registration_ransac_based_on_feature_matching(
        src, tgt, src_fpfh, tgt_fpfh, True, voxel_size * 1.5,
        o3d.pipelines.registration.TransformationEstimationPointToPoint(False), 4,
        [
            o3d.pipelines.registration.CorrespondenceCheckerBasedOnEdgeLength(0.9),
            o3d.pipelines.registration.CorrespondenceCheckerBasedOnDistance(voxel_size * 1.5)
        ],
        o3d.pipelines.registration.RANSACConvergenceCriteria(4000000, 100)
    )

def refine_icp(src, tgt, init_trans, voxel_size):
    return o3d.pipelines.registration.registration_icp(
        src, tgt, voxel_size * 0.4, init_trans,
        o3d.pipelines.registration.TransformationEstimationPointToPlane()
    )

def register_laz(before_path, after_path, voxel_size=2.0):
    after_folder = Path(after_path).parent
    adjusted_path = after_folder / "after-adjusted.laz"

    print("Loading point clouds...")
    before_pcd, before_las = load_laz_as_pcd(before_path)
    after_pcd, after_las = load_laz_as_pcd(after_path)
    crs = before_las.header.parse_crs()

    print("Computing intersection bounding box...")
    bbox_before = before_pcd.get_axis_aligned_bounding_box()
    bbox_after = after_pcd.get_axis_aligned_bounding_box()

    # Intersect AABB
    min_bound = np.maximum(bbox_before.get_min_bound(), bbox_after.get_min_bound())
    max_bound = np.minimum(bbox_before.get_max_bound(), bbox_after.get_max_bound())

    if np.any(min_bound >= max_bound):
        raise ValueError("No overlapping region between point clouds.")

    intersection_bbox = o3d.geometry.AxisAlignedBoundingBox(min_bound, max_bound)
    before_pcd = before_pcd.crop(intersection_bbox)
    after_pcd = after_pcd.crop(intersection_bbox)

    print(f"Cropped to intersection: {before_pcd} and {after_pcd}")

    print("Preprocessing...")
    before_down, before_fpfh = preprocess(before_pcd, voxel_size)
    after_down, after_fpfh = preprocess(after_pcd, voxel_size)

    print("Running global alignment...")
    ransac_result = global_align(after_down, before_down, after_fpfh, before_fpfh, voxel_size)

    # print("Refining with ICP...")
    # before_pcd.estimate_normals(
    #     o3d.geometry.KDTreeSearchParamHybrid(radius=voxel_size * 2, max_nn=30)
    # )
    # after_pcd.estimate_normals(
    #     o3d.geometry.KDTreeSearchParamHybrid(radius=voxel_size * 2, max_nn=30)
    # )

    # icp_result = refine_icp(after_pcd, before_pcd, ransac_result.transformation, 0.5)


    print("Applying transformation and saving...")
    # Transform full original point cloud (not cropped)
    full_after_pcd, _ = load_laz_as_pcd(after_path)
    full_after_pcd.transform(ransac_result.transformation)

    # Apply transformation to original LAS data
    save_pcd_as_laz(full_after_pcd, crs, adjusted_path)

    print(f"Saved adjusted point cloud to: {adjusted_path}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python register_laz.py before.laz after.laz")
    else:
        register_laz(sys.argv[1], sys.argv[2])
