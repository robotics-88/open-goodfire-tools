#!/bin/bash

# Abort script on error, errors include pre-pipe commands
set -eo pipefail

packages_to_install="libudunits2-dev libgdal-dev libgeos-dev libproj-dev libxml2-dev"

# Venv dep
packages_to_install="$packages_to_install python3-venv"

# do not use -y; give the user a chance to review dependencies before they install
sudo apt install $packages_to_install

# create venv, install python deps
if [ -d "../.env" ]; then
    echo ".env virtual environment already exists. Skipping setup."
else
    pushd ..
    python3 -m venv .env
    source .env/bin/activate
    pip install -r requirements.txt
    popd
fi

# Run R script to install R dependencies
Rscript rdependency_install.R