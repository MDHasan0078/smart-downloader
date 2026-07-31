#!/bin/bash
# Builds the .deb package from source. Run from the repo root:
#   ./scripts/build_deb.sh
#
# Output: simple-yt-downloader_<version>_all.deb in the repo root.
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$(mktemp -d)"
PKG_DIR="$BUILD_DIR/pkg"

VERSION=$(grep -oP '(?<=Version: ).*' "$REPO_ROOT/packaging/control")
echo "Building simple-yt-downloader version $VERSION..."

mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR/usr/lib/simple-yt-downloader"
mkdir -p "$PKG_DIR/usr/bin"
mkdir -p "$PKG_DIR/usr/share/applications"
mkdir -p "$PKG_DIR/usr/share/icons"
mkdir -p "$PKG_DIR/usr/share/doc/simple-yt-downloader"

cp "$REPO_ROOT/packaging/control" "$PKG_DIR/DEBIAN/control"
cp "$REPO_ROOT/packaging/postinst" "$PKG_DIR/DEBIAN/postinst"
cp "$REPO_ROOT/packaging/postrm" "$PKG_DIR/DEBIAN/postrm"
cp "$REPO_ROOT/packaging/simple-yt-downloader.desktop" "$PKG_DIR/usr/share/applications/"
cp -r "$REPO_ROOT/packaging/icons/hicolor" "$PKG_DIR/usr/share/icons/"
cp "$REPO_ROOT/LICENSE" "$PKG_DIR/usr/share/doc/simple-yt-downloader/copyright"
gzip -n -9 -c "$REPO_ROOT/packaging/changelog" > "$PKG_DIR/usr/share/doc/simple-yt-downloader/changelog.gz"
cp -r "$REPO_ROOT/simple_yt_downloader" "$PKG_DIR/usr/lib/simple-yt-downloader/"

# Launcher: adds the installed package dir to sys.path and runs it.
cat > "$PKG_DIR/usr/bin/simple-yt-downloader" << 'EOF'
#!/usr/bin/env python3
import sys
sys.path.insert(0, "/usr/lib/simple-yt-downloader")
from simple_yt_downloader.app import main
if __name__ == "__main__":
    sys.exit(main())
EOF

find "$PKG_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$PKG_DIR" -name "*.pyc" -delete

chmod 755 "$PKG_DIR/DEBIAN" "$PKG_DIR/DEBIAN/postinst" "$PKG_DIR/DEBIAN/postrm"
chmod 644 "$PKG_DIR/DEBIAN/control"
chmod 755 "$PKG_DIR/usr/bin/simple-yt-downloader"
find "$PKG_DIR/usr/lib" -type f -exec chmod 644 {} \;
find "$PKG_DIR/usr/share" -type f -exec chmod 644 {} \;
find "$PKG_DIR" -type d -exec chmod 755 {} \;

dpkg-deb --build --root-owner-group "$PKG_DIR" "$REPO_ROOT/simple-yt-downloader_${VERSION}_all.deb"
rm -rf "$BUILD_DIR"

echo "Built: simple-yt-downloader_${VERSION}_all.deb"
