#!/usr/bin/env Rscript

# Check arguments
args <- commandArgs(trailingOnly=TRUE)
if (length(args) < 2) {
  stop("Must specify at least 2 arguments", call.=FALSE)
}

las_path <- args[1]
dem_path <- args[2]
chm_path <- args[3]
segmented_path <- args[4]

overwrite <- if (length(args) > 2 & args[3] == "-o") TRUE else FALSE

# Load dependencies
library("lasR")

# ground classification, DTM & “standard” CHM (optional)
classify_alg  <- classify_with_csf()
dtm_alg       <- dtm(1, ofile = dem_path)
chm_write_alg <- chm(1, ofile = chm_path)

# assemble the full pipeline and execute
full_pipeline <- classify_alg   +
                 dtm_alg        +
                 chm_write_alg

exec(full_pipeline, on = las_path, ncores = 16, progress = TRUE)

library(terra)

# Load rasters to mask DEM, CHM is only present in lidar range areas
dem <- rast(dem_path)
chm <- rast(chm_path)

# Mask DEM where CHM is NA
dem_masked <- mask(dem, chm)

# Overwrite the DEM with masked version
writeRaster(dem_masked, dem_path, overwrite=TRUE)


# Now use DEM to convert CHM to AGL altitudes
cbh_agl  <- chm - dem

# (optional) mask out non‐canopy areas:
cbh_agl_masked <- mask(cbh_agl, chm)

# overwrite or write out new file
writeRaster(cbh_agl_masked, chm_path, overwrite=TRUE)