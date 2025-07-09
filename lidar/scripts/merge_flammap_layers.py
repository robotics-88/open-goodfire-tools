import rasterio
import rasterio.warp
import numpy as np

def generate_merged_data(flammap_path, dem_path, chm_path, aspect_path, slope_path, merged_path):
    # Open input files
    with rasterio.open(flammap_path) as flammap_file, \
         rasterio.open(dem_path) as dem_file, \
         rasterio.open(chm_path) as chm_file, \
         rasterio.open(aspect_path) as aspect_file, \
         rasterio.open(slope_path) as slope_file:

        target_crs = dem_file.crs
        target_shape = dem_file.shape
        target_transform = dem_file.transform
        target_dtype = dem_file.dtypes[0]

        desc_map = {
            'US_ELEV2020': dem_file,
            'US_220CBH_22': chm_file,
            'US_ASP2020': aspect_file,
            'US_SLPD2020': slope_file,
        }

        with rasterio.open(merged_path, 'w', driver=flammap_file.driver,
                           height=target_shape[0], width=target_shape[1],
                           count=len(flammap_file.indexes),
                           dtype=target_dtype,
                           crs=target_crs, transform=target_transform) as merged_file:

            for i, description in zip(flammap_file.indexes, flammap_file.descriptions):

                if description in desc_map:
                    # Reproject both user and flammap data to target grid
                    user_src = desc_map[description]
                    user_data = np.zeros(target_shape, dtype=target_dtype)
                    fallback_data = np.zeros(target_shape, dtype=target_dtype)

                    rasterio.warp.reproject(
                        source=rasterio.band(user_src, 1),
                        destination=user_data,
                        dst_transform=target_transform,
                        dst_crs=target_crs,
                        resampling=rasterio.warp.Resampling.nearest
                    )

                    rasterio.warp.reproject(
                        source=rasterio.band(flammap_file, i),
                        destination=fallback_data,
                        dst_transform=target_transform,
                        dst_crs=target_crs,
                        resampling=rasterio.warp.Resampling.nearest
                    )

                    # Fuse user data with fallback (FlamMap) data
                    # Use nodata from user raster or assume 0 if missing
                    nodata_val = user_src.nodata
                    if nodata_val is not None:
                        user_mask = (user_data == nodata_val)
                    else:
                        # Guess a nodata value only if no nodata is defined
                        most_common = np.bincount(user_data.flatten()).argmax()
                        ratio = np.sum(user_data == most_common) / user_data.size
                        user_mask = (user_data == most_common) if ratio > 0.95 else np.full(user_data.shape, False)

                    if description == 'US_ELEV2020':
                        # Special case for US_ELEV2020
                        user_mask = np.isnan(user_data) | (user_data == 0)

                    fused = np.where(user_mask, fallback_data, user_data)

                    merged_file.write(fused.astype(target_dtype), i)

                else:
                    resampling_method = (
                        rasterio.warp.Resampling.nearest
                        if description == 'US_240FBFM40'
                        else rasterio.warp.Resampling.bilinear
                    )

                    rasterio.warp.reproject(
                        source=rasterio.band(flammap_file, i),
                        destination=rasterio.band(merged_file, i),
                        dst_transform=target_transform,
                        dst_crs=target_crs,
                        resampling=resampling_method
                    )

                merged_file.set_band_description(i, description)
