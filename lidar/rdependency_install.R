#!/usr/bin/env Rscript

install.packages(c(
  "lidR",          # LiDAR processing (more tools)
  "terra",         # Raster processing
  "rlandfire"      # Landfire API
))

# LiDAR processing (fewer but faster tools)
install.packages('lasR', repos = 'https://r-lidar.r-universe.dev')