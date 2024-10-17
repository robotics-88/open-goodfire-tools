#!/usr/bin/env Rscript

# Check arguments
args <- commandArgs(trailingOnly=TRUE)
if (length(args) < 2) {
  stop("Must specify at least 2 arguments", call.=FALSE)
}

las_path <- args[1]
dem_path <- args[2]

overwrite <- if (length(args) > 2 & args[3] == "-o") TRUE else FALSE

# Load dependencies
library("lidR")

# Load file
las <- readLAS(las_path)

# Classify ground points
las <- classify_ground(las, algorithm = csf())

# Drape a cloth on it
dtm_cloth <- rasterize_terrain(las, algorithm = knnidw(k = 10L, p = 2))

# Save output
terra::writeRaster(dtm_cloth, dem_path, overwrite = overwrite)