#!/bin/bash

set -e

# Get version from git tag (no 'v' prefix to remove)
VERSION="${GITHUB_REF_NAME}"
DIST_DIR="dist"
PACKAGE_NAME="webapp-manager-qt-$VERSION"

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf $DIST_DIR

# Build translations
echo "Building translations..."
make buildmo

# Build the project
echo "Building the project..."
mkdir -p $DIST_DIR/$PACKAGE_NAME

# Copy only the usr directory (contains all runtime files)
echo "Copying runtime files..."
cp -r usr $DIST_DIR/$PACKAGE_NAME/

# Copy documentation files
echo "Copying documentation..."
cp README.md $DIST_DIR/$PACKAGE_NAME/
cp LICENSE $DIST_DIR/$PACKAGE_NAME/

# Package the application
echo "Packaging the application..."
tar -czf $DIST_DIR/webapp-manager-qt-$VERSION.tar.gz -C $DIST_DIR $PACKAGE_NAME

echo "Release preparation complete. Version: $VERSION"
echo "Package created at: $DIST_DIR/webapp-manager-qt-$VERSION.tar.gz"