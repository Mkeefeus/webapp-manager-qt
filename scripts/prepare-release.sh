#!/bin/bash

set -e

# Get version from git tag (no 'v' prefix to remove)
VERSION="${GITHUB_REF_NAME}"
DIST_DIR="dist"
PACKAGE_NAME="webapp-manager-qt-$VERSION"

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf $DIST_DIR

# Build the project
echo "Building the project..."
mkdir -p $DIST_DIR/$PACKAGE_NAME

# Copy all files except excluded ones
echo "Copying files..."
rsync -av \
  --exclude='.git' \
  --exclude='.github/' \
  --exclude='.copr/' \
  --exclude='create-source-tarball.sh' \
  --exclude='.gitignore' \
  --exclude='dist/' \
  --exclude='scripts/' \
  ./ $DIST_DIR/$PACKAGE_NAME/

# Package the application (from parent directory, not inside dist)
echo "Packaging the application..."
tar -czf $DIST_DIR/webapp-manager-qt-$VERSION.tar.gz -C $DIST_DIR $PACKAGE_NAME

echo "Release preparation complete. Version: $VERSION"
echo "Package created at: $DIST_DIR/webapp-manager-qt-$VERSION.tar.gz"