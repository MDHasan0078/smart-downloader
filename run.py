#!/usr/bin/env python3
"""Run Simple YT Downloader directly from a source checkout, no install
needed -- useful for development. The installed .deb version instead uses
packaging/simple-yt-downloader.desktop -> a launcher at /usr/bin that points
at /usr/lib/simple-yt-downloader (see scripts/build_deb.sh).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from simple_yt_downloader.app import main

if __name__ == "__main__":
    sys.exit(main())
