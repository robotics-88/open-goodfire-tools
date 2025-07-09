import laspy
import numpy as np
import rasterio
from rasterio.transform import from_origin
from scipy.stats import binned_statistic_2d
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.colors as colors
from matplotlib.colors import Normalize

def load_las_or_laz(filepath):
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    las = laspy.read(filepath)
    return np.vstack((las.x, las.y, las.z)).T

def find_las_or_laz(base_path, stem):
    for ext in [".laz", ".las"]:
        file_path = base_path / f"{stem}{ext}"
        if file_path.exists():
            return file_path
    raise FileNotFoundError(f"Could not find {stem}.las or {stem}.laz in {base_path}")

def compute_density_grid(points, xmin, xmax, ymin, ymax, resolution, stat='count'):
    xmin = np.floor(xmin)
    xmax = np.ceil(xmax)
    ymin = np.floor(ymin)
    ymax = np.ceil(ymax)

    if (xmax - xmin) / resolution > 10000 or (ymax - ymin) / resolution > 10000:
        raise ValueError("Bounding box too large. Check input data or resolution.")

    x_bins = np.arange(xmin, xmax + resolution, resolution)
    y_bins = np.arange(ymin, ymax + resolution, resolution)

    values = None
    if stat == 'count':
        values = None
    elif stat in ('mean', 'sum'):
        values = points[:, 2]  # Z values
    else:
        raise ValueError(f"Unsupported stat: {stat}")

    grid, _, _, _ = binned_statistic_2d(
        points[:, 1], points[:, 0],  # y, x
        values,
        statistic=stat,
        bins=[y_bins, x_bins]
    )
    return grid, x_bins, y_bins

def compute_fuel_volume(before_file, after_file, output_folder, resolution=1.0):
    output_file = output_folder / "volume_difference.tif"
    resolution = 1.0
    with laspy.open(before_file) as lasf:
        crs = lasf.header.parse_crs()
        if crs is not None:
            crs_wkt = crs.to_wkt()
        else:
            crs_wkt = "EPSG:32610"  # fallback if CRS not found. Only correct for parts of Western US/Canada!

    before_pts = load_las_or_laz(before_file)
    after_pts = load_las_or_laz(after_file)

    all_x = np.hstack((before_pts[:, 0], after_pts[:, 0]))
    all_y = np.hstack((before_pts[:, 1], after_pts[:, 1]))
    xmin, xmax = all_x.min(), all_x.max()
    ymin, ymax = all_y.min(), all_y.max()

    before_grid, x_edges, y_edges = compute_density_grid(before_pts, xmin, xmax, ymin, ymax, resolution, stat='mean')
    after_grid, _, _ = compute_density_grid(after_pts, xmin, xmax, ymin, ymax, resolution, stat='mean')
    diff_grid = after_grid - before_grid
    diff_grid = np.where(np.isnan(diff_grid), 0, diff_grid)  # or use np.nanmean when binning

    transform = from_origin(x_edges[0], y_edges[-1], resolution, resolution)

    nodata_val = -9999.0
    # Cells that are valid in both before and after
    valid_mask = ~np.isnan(before_grid) & ~np.isnan(after_grid)

    # Compute difference only where both are valid
    diff_grid = np.full(before_grid.shape, nodata_val, dtype=np.float32)
    diff_grid[valid_mask] = before_grid[valid_mask] - after_grid[valid_mask]

    diff_grid = np.flipud(diff_grid)  # Flip the grid to match the rasterio convention

    with rasterio.open(
        output_file, "w",
        driver="GTiff",
        height=diff_grid.shape[0],
        width=diff_grid.shape[1],
        count=1,
        dtype=diff_grid.dtype,
        crs=crs_wkt,
        transform=transform,
        nodata=nodata_val
    ) as dst:
        dst.write(diff_grid, 1)


    print(f"✅ Saved: {output_file}")

    # Auto compute contrast range for difference
    valid_diff = diff_grid[diff_grid != nodata_val]
    vmin_d, vmax_d = np.percentile(valid_diff, [2, 98])
    print(f"Difference grid vmin: {vmin_d}, vmax: {vmax_d}")
    norm = Normalize(vmin=vmin_d, vmax=vmax_d)

    fig, axs = plt.subplots(1, 3, figsize=(15, 6))

    # BEFORE
    im0 = axs[0].imshow(np.flipud(before_grid), cmap='viridis', vmin=vmin_d, vmax=vmax_d)
    axs[0].set_title("Before Mean Height")
    axs[0].axis('off')
    fig.colorbar(im0, ax=axs[0], fraction=0.046)

    # AFTER
    im1 = axs[1].imshow(np.flipud(after_grid), cmap='viridis', vmin=vmin_d, vmax=vmax_d)
    axs[1].set_title("After Mean Height")
    axs[1].axis('off')
    fig.colorbar(im1, ax=axs[1], fraction=0.046)

    # DIFFERENCE
    im2 = axs[2].imshow(diff_grid, cmap='RdBu', norm=norm)
    axs[2].set_title("Difference (Before - After)")
    axs[2].axis('off')
    fig.colorbar(im2, ax=axs[2], fraction=0.046)

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python fuelvolume.py before.laz after.laz output_folder")
        sys.exit(1)
    compute_fuel_volume(sys.argv[1], sys.argv[2], sys.argv[3])
