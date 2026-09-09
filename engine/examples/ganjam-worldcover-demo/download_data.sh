#!/usr/bin/env bash
set -euo pipefail

demo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
demo_data_directory="$demo_root/data"
mkdir -p "$demo_data_directory"

download_demo_raster() {
  demo_url="$1"
  demo_filename="$2"
  demo_destination="$demo_data_directory/$demo_filename"
  demo_partial="$demo_destination.part"

  if [[ -s "$demo_destination" ]]; then
    echo "Already downloaded: $demo_filename"
    return
  fi

  echo "Downloading $demo_filename"
  curl --fail --location --retry 3 --continue-at - \
    --output "$demo_partial" "$demo_url"
  mv "$demo_partial" "$demo_destination"
}

download_demo_raster \
  "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v100/2020/map/ESA_WorldCover_10m_2020_v100_N18E084_Map.tif" \
  "ESA_WorldCover_10m_2020_v100_N18E084_Map.tif"

download_demo_raster \
  "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N18E084_Map.tif" \
  "ESA_WorldCover_10m_2021_v200_N18E084_Map.tif"

echo "WorldCover demonstration inputs are ready."
