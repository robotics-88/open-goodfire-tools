#!/usr/bin/env Rscript

# Check arguments
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) {
  stop("Must specify at least 2 arguments", call. = FALSE)
}

las_path <- args[1]
chm_path <- args[2]

overwrite <- if (length(args) > 2 & args[3] == "-o") TRUE else FALSE

# Load dependencies
print("Loading libraries...")
library("lidR")

# Load file
print("Loading LAS file...")
las <- readLAS(las_path)

# Classify ground points
print("Computing CHM...")
chm <- rasterize_canopy(las, 0.5, pitfree(subcircle = 0.2))

# Save output
print("Saving CHM...")
terra::writeRaster(chm, chm_path, overwrite = overwrite)