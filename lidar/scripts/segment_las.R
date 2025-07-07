#!/usr/bin/env Rscript

# Check arguments
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 3) {
  stop("Must specify at least 3 arguments", call. = FALSE)
}

las_path <- args[1]
chm_path <- args[2]
las_out_path <- args[3]

overwrite <- if (length(args) > 3 & args[4] == "-o") TRUE else FALSE


# Load dependencies
library("lidR")

# Load files
print("Loading files...")
las <- readLAS(las_path)
chm <- terra::rast(chm_path)

# Find treetops
print("Finding Trees...")
f <- function(x) {
  y <- 2.6 * (-(exp(-0.08*(x-2)) - 1)) + 3
  y[x < 2] <- 3
  y[x > 20] <- 5
  return(y)
}

ttops <- locate_trees(chm, lmf(ws = 3, hmin = 2))

# Segment point cloud
print("Segmenting...")
algo  <- dalponte2016(chm_res, ttops, th_seed = 2, th = 1.5)
las <- segment_trees(las, algo)

# Save output
print("Saving Output...")
writeLAS(las, las_out_path)