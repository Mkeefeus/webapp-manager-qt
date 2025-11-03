#!/bin/bash

# Configuration
NAME="webapp-manager"
VERSION="1.0.0"
TARBALL="${NAME}-${VERSION}.tar.gz"
SOURCES_DIR="$HOME/rpmbuild/SOURCES"

# Create temporary directory for packaging
TEMP_DIR=$(mktemp -d)
BUILD_DIR="${TEMP_DIR}/${NAME}-${VERSION}"

echo "Creating source tarball for ${NAME} ${VERSION}..."

# Create build directory structure
mkdir -p "${BUILD_DIR}"

# Copy project files
cp -r usr "${BUILD_DIR}/"
cp -r po "${BUILD_DIR}/"
cp Makefile "${BUILD_DIR}/"
cp makepot "${BUILD_DIR}/"
cp webapp-manager.pot "${BUILD_DIR}/"
cp LICENSE "${BUILD_DIR}/"
cp README.md "${BUILD_DIR}/"
cp .gitignore "${BUILD_DIR}/"

# Remove Python cache files
find "${BUILD_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "${BUILD_DIR}" -type f -name "*.pyc" -delete 2>/dev/null || true
find "${BUILD_DIR}" -type f -name "*.pyo" -delete 2>/dev/null || true

# Remove any existing mo files (they'll be built during rpm build)
find "${BUILD_DIR}/usr/share/locale" -type f -name "*.mo" -delete 2>/dev/null || true

# Create tarball
cd "${TEMP_DIR}"
tar -czf "${TARBALL}" "${NAME}-${VERSION}"

# Ensure SOURCES directory exists
mkdir -p "${SOURCES_DIR}"

# Copy tarball to rpmbuild SOURCES
cp "${TARBALL}" "${SOURCES_DIR}/"

# Cleanup
cd -
rm -rf "${TEMP_DIR}"

echo "✓ Created ${TARBALL}"
echo "✓ Copied to ${SOURCES_DIR}/${TARBALL}"
echo ""
echo "You can now build the RPM with:"
echo "  rpmbuild -ba webapp-manager.spec"