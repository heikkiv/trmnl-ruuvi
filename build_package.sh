#!/bin/bash
set -e

PACKAGE_DIR="lambda_package"
ZIP_FILE="lambda_deployment.zip"

echo "Cleaning up previous build..."
rm -rf "$PACKAGE_DIR" "$ZIP_FILE"
mkdir -p "$PACKAGE_DIR"

echo "Installing dependencies..."
pip install -r requirements.txt -t "$PACKAGE_DIR" --quiet

echo "Copying Lambda handler..."
cp lambda_function.py "$PACKAGE_DIR/"

echo "Zipping package..."
cd "$PACKAGE_DIR"
zip -r "../$ZIP_FILE" . -x "*.pyc" -x "*/__pycache__/*"
cd ..

echo "Done: $ZIP_FILE ($(du -sh $ZIP_FILE | cut -f1))"
