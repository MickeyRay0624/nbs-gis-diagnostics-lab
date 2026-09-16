"""Download small, user-generated Code Editor exports from an ignored JSON file.

The transient JSON maps output stems to signed URLs. It is deleted after use;
public provenance uses stable collection IDs, never generated download URLs.
"""

import concurrent.futures
import json
import sys
import time
from pathlib import Path
import requests
import rasterio
from step2_package import CACHE

links_path = Path(sys.argv[1])
links = json.loads(links_path.read_text())


def fetch(item):
    name, url = item
    if not name.replace("-", "").replace("_", "").replace(".", "").isalnum():
        raise ValueError("Invalid output filename")
    path = CACHE / f"{name}.tif"
    if path.exists():
        with rasterio.open(path) as s:
            if s.count and s.width:
                return f"{name}: cached"
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=300)
            response.raise_for_status()
            with rasterio.MemoryFile(response.content) as mem:
                with mem.open() as s:
                    if not s.count:
                        raise ValueError("Empty raster")
            path.write_bytes(response.content)
            return f"{name}: {len(response.content)} bytes"
        except Exception as error:
            if attempt == 2:
                # Avoid echoing signed URLs in network exception messages.
                return f"{name}: FAILED ({type(error).__name__})"
            time.sleep(3)


try:
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(fetch, links.items()))
    for result in results:
        print(result, flush=True)
    if any("FAILED" in result for result in results):
        raise SystemExit(1)
finally:
    links_path.unlink(missing_ok=True)
