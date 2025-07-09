#!/bin/bash
set -euo pipefail

# Base URL for Hugging Face raw files
BASE_URL="https://huggingface.co/datasets/Robotics88/goodfire/resolve/main/test"

# Destination folder
DEST_DIR="data/test/input"
mkdir -p "$DEST_DIR"

# List of files in test/ on Hugging Face
FILES=(
    "before/before.laz"
    "after/after.laz"
)

mkdir -p "$DEST_DIR/before"
mkdir -p "$DEST_DIR/after"

echo "📥 Downloading test data to $DEST_DIR..."
for file in "${FILES[@]}"; do
    echo "Downloading $file..."
    wget -q --show-progress "$BASE_URL/input/$file" -O "$DEST_DIR/$file"
done

echo "✅ All files downloaded to $DEST_DIR."
