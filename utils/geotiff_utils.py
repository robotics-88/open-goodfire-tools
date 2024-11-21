
import rasterio ,rasterio.warp


def get_lat_long_bounds(geotiff_path):
    with rasterio.open( geotiff_path ) as geotiff_file:
        # transform to EPSG:4328 (Geocentric lat long)

        print(f'Original bounds in {geotiff_file.crs}')
        print(geotiff_file.bounds)
        print(f'Converted bounds in {rasterio.crs.CRS.from_epsg(4328)}')
        print(rasterio.warp.transform_bounds(geotiff_file.crs, rasterio.crs.CRS.from_epsg(4328), *geotiff_file.bounds))
    

        return rasterio.warp.transform_bounds(geotiff_file.crs, rasterio.crs.CRS.from_epsg(4328), *geotiff_file.bounds)
    

def reporoject(geotiff, dst_crs):
    
    dst_transform = rasterio.warp.calculate_default_transform(geotiff, dst_crs)
    
    # I would initialize this as an out file, except I think I would prefer to keep this in RAM for the moment
    destination = None

    for i in geotiff.indexes:
        rasterio.warp.reproject(rasterio.band(geotiff, i), rasterio.band(destination, i), geotiff.transform, geotiff.crs, dst_transform, dst_crs, resampling=rasterio.warp.Resampling.average)

    return destination
    
