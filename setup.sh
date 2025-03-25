#!/bin/bash

# Abort script on error, errors include pre-pipe commands
set -eo pipefail

# Check for nvidia graphics drivers
if ! command -v nvidia-smi &> /dev/null; then
    echo "---------------------------------------------------------------------------------------------------------------"
    echo "---  Please install nvidia graphics drivers and try again                                                   ---"
    echo "---    On Ubuntu, do this via the \"Additional Drivers\" app                                                  ---"
    echo "---    More info: https://documentation.ubuntu.com/server/how-to/graphics/install-nvidia-drivers/index.html ---"
    echo "---------------------------------------------------------------------------------------------------------------"
        
    exit
fi


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
# Configure nvidia dep
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# do not use -y; give the user a chance to review dependencies before they install
sudo apt install $packages_to_install

# Test if nvidia runtime works
if ! docker run --rm --runtime=nvidia --gpus all nvidia/cuda:12.4.0-devel-ubuntu22.04 nvidia-smi; then

    # Add nvidia as a docker runtime
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
source .env/bin/activate
pip install -r requirements.txt


# pull submodules
git submodule update --init --recursive
root_dir=$(pwd)

# build openmvg
mkdir -p $root_dir/depend/openMVG/build
cd $root_dir/depend/openMVG/build

cmake -DCMAKE_BUILD_TYPE=RELEASE ../src/
cmake --build .

# build OpenSplat
cd $root_dir/depend/OpenSplat
docker buildx build -t open_splat:latest .


# TODO: R dependencies