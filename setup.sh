#!/bin/bash

# Abort script on error, errors include pre-pipe commands
set -eo pipefail


packages_to_install=""

# Venv dep
packages_to_install="$packages_to_install python3-venv"

# Nvidia dep
packages_to_install="$packages_to_install nvidia-container-toolkit"

# OpenMVG deps
packages_to_install="$packages_to_install libpng-dev libjpeg-dev libtiff-dev libxxf86vm1 libxxf86vm-dev libxi-dev libxrandr-dev"

# Docker dep
if ! command -v docker &> /dev/null; then
    packages_to_install="$packages_to_install docker.io docker-buildx"
fi

# Install dependencies
# do not use -y; give the user a chance to review dependencies before they install
sudo apt install $packages_to_install

# Add nvidia as a docker runtime
# Test if nvidia runtime works
if ! docker run --rm --runtime=nvidia --gpus all nvidia/cuda:12.4.0-devel-ubuntu22.04 nvidia-smi; then
    sudo usermod -aG docker $USER
    sudo nvidia-ctk runtime configure --runtime=docker
    sudo systemctl restart docker

    # Test nvidia runtime again, just in case
    if ! docker run --rm --runtime=nvidia --gpus all nvidia/cuda:12.4.0-devel-ubuntu22.04 nvidia-smi; then
        echo "---------------------------------------------------------------"
        echo "--- Please restart your machine, then run this script again ---"
        echo "---------------------------------------------------------------"
        exit
    fi
fi

# create venv, install python deps
python3 -m venv .env
./env/bin/activate
pip install -r requirements.txt


# pull submodules
git submodule update --init --recursive
root_dir=$pwd


# build openmvg
mkdir $root_dir/depend/OpenSplat/build
cd $root_dir/depend/OpenSplat/build

cmake -DCMAKE_BUILD_TYPE=RELEASE ../src/
cmake --build .

# build OpenSplat
cd $root_dir/depend/OpenSplat
docker buildx build -t open_splat:latest .


# TODO: R dependencies