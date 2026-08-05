#!/usr/bin/env bash
#
# Build a minimal static ffmpeg + ffprobe for Smart Downloader.
#
# Works on Linux (gcc), macOS (clang), and Windows CI (MSYS2 MINGW64). Produces
# a lean LGPL build containing only the codecs the app needs:
#   - remux/merge of mp4 + webm/mkv (yt-dlp bestvideo+bestaudio)
#   - audio extraction to mp3 (libmp3lame), flac, opus, aac, vorbis
#
# Usage:
#   build_ffmpeg.sh <src_dir> <prefix_dir>
#
#   src_dir   directory where the ffmpeg source will be cloned (created if
#             missing). A shallow clone is fetched from the GitHub mirror
#             (fallback: git.ffmpeg.org).
#   prefix_dir  installation prefix; ffmpeg + ffprobe land in $prefix/bin.
#
# Examples:
#   build_ffmpeg.sh /tmp/ffmpeg-src /tmp/ffmpeg-min
#   (inside MSYS2 MINGW64 shell on Windows runners)
#
# Result size on Linux: ffmpeg ~4.3 MB + ffprobe ~4.1 MB (vs 169 MB gpl zip).
#
# Requires: make, gcc (or mingw-w64 gcc on MSYS2, or clang on macOS),
#           libmp3lame-dev, libopus-dev (Linux) / mingw-w64-x86_64-lame, -opus
#           (MSYS2) / pkg-config + network (macOS: lame+opus built statically
#           from source here so the binary is self-contained).

set -euo pipefail

SRC_DIR="${1:?usage: build_ffmpeg.sh <src_dir> <prefix_dir>}"
PREFIX="${2:?usage: build_ffmpeg.sh <src_dir> <prefix_dir>}"
JOBS="${JOBS:-$(nproc 2>/dev/null || echo 4)}"
FFMPEG_TAG="${FFMPEG_TAG:-n7.1.1}"
FFMPEG_REPO="${FFMPEG_REPO:-https://github.com/FFmpeg/FFmpeg}"
FFMPEG_REPO_FALLBACK="${FFMPEG_REPO_FALLBACK:-https://git.ffmpeg.org/ffmpeg}"

# Download with retries; on failure, try the fallback mirror. Any remaining
# error propagates and aborts the build (set -e).
download_tarball() {
  local primary="$1" fallback="$2" dest="$3"
  if ! curl -fsSL --retry 3 --retry-delay 2 -o "$dest" "$primary"; then
    echo "warning: $primary failed, trying fallback $fallback" >&2
    curl -fsSL --retry 3 --retry-delay 2 -o "$dest" "$fallback"
  fi
}

EXTRA_CFLAGS=""
EXTRA_LDFLAGS=""

# macOS: Homebrew lame/opus are dylibs (leak onto brew Cellar paths). Build
# static archives from source so the ffmpeg binary is self-contained.
if [ "$(uname -s)" = "Darwin" ]; then
  DEPS_PREFIX="$PREFIX/deps"
  mkdir -p "$DEPS_PREFIX"

  if [ ! -f "$DEPS_PREFIX/lib/libmp3lame.a" ]; then
    download_tarball \
      "https://downloads.sourceforge.net/lame/lame-3.100.tar.gz" \
      "https://sourceforge.net/projects/lame/files/lame/3.100/lame-3.100.tar.gz/download" \
      "$SRC_DIR/../lame-3.100.tar.gz"
    tar -xzf "$SRC_DIR/../lame-3.100.tar.gz" -C "$SRC_DIR/.."
    (
      cd "$SRC_DIR/../lame-3.100"
      ./configure --disable-shared --enable-static --disable-frontend --prefix="$DEPS_PREFIX"
      make -j"$JOBS"
      make install
    )
  fi

  if [ ! -f "$DEPS_PREFIX/lib/libopus.a" ]; then
    download_tarball \
      "https://downloads.xiph.org/releases/opus/opus-1.5.2.tar.gz" \
      "https://github.com/xiph/opus/releases/download/v1.5.2/opus-1.5.2.tar.gz" \
      "$SRC_DIR/../opus-1.5.2.tar.gz"
    tar -xzf "$SRC_DIR/../opus-1.5.2.tar.gz" -C "$SRC_DIR/.."
    (
      cd "$SRC_DIR/../opus-1.5.2"
      ./configure --disable-shared --enable-static --disable-doc --prefix="$DEPS_PREFIX"
      make -j"$JOBS"
      make install
    )
  fi

  export PKG_CONFIG_PATH="$DEPS_PREFIX/lib/pkgconfig"
  EXTRA_CFLAGS="-I$DEPS_PREFIX/include"
  EXTRA_LDFLAGS="-L$DEPS_PREFIX/lib"
fi

if [ ! -d "$SRC_DIR/.git" ]; then
  if ! git clone --depth 1 --branch "$FFMPEG_TAG" "$FFMPEG_REPO" "$SRC_DIR"; then
    echo "warning: clone from $FFMPEG_REPO failed, trying fallback $FFMPEG_REPO_FALLBACK" >&2
    rm -rf "$SRC_DIR"
    git clone --depth 1 --branch "$FFMPEG_TAG" "$FFMPEG_REPO_FALLBACK" "$SRC_DIR"
  fi
fi

cd "$SRC_DIR"

./configure \
  --prefix="$PREFIX" \
  --extra-cflags="$EXTRA_CFLAGS" \
  --extra-ldflags="$EXTRA_LDFLAGS" \
  --prefix="$PREFIX" \
  --disable-everything \
  --disable-doc \
  --disable-debug \
  --disable-autodetect \
  --disable-network \
  --disable-asm \
  --disable-avdevice \
  --enable-ffmpeg \
  --enable-ffprobe \
  --enable-small \
  --enable-stripping \
  --enable-swscale \
  --enable-protocol=file,pipe,concat \
  --enable-decoder=aac,h264,hevc,vp9,av1,opus,vorbis,mp3,flac,alac,pcm_s16le,mpeg4,mjpeg \
  --enable-encoder=libmp3lame,flac,libopus,aac,pcm_s16le,vorbis \
  --enable-muxer=mp4,mov,matroska,webm,mp3,flac,ogg,wav,ipod,opus \
  --enable-demuxer=mov,mp4,m4a,3gp,3g2,mj2,matroska,webm,ogg,mp3,flac,wav,aac,opus \
  --enable-parser=aac,h264,hevc,vp9,av1,opus,vorbis,mp3,flac,mpeg4video,mjpeg \
  --enable-bsf=aac_adtstoasc,h264_mp4toannexb,hevc_mp4toannexb,vp9_superframe,vp9_raw_reorder \
  --enable-filter=aresample,aformat,anull,asetnsamples,apad,atrim \
  --enable-libmp3lame \
  --enable-libopus \
  --enable-swresample \
  --enable-avformat \
  --enable-avcodec \
  --enable-avutil

make -j"$JOBS"
make install

echo "=== built ffmpeg binaries ==="
ls -lh "$PREFIX/bin/"
