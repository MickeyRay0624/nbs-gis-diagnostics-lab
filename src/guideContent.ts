export const guideContent = {
  "title": "How to use each feature and understand the calculations",
  "lead": "Choose one of the seven diagnostics. For land cover and forest, keep Ganjam 2002/2012/2022, 50 m cells and 50 m edge width, then run. Other modules use prepared numeric inputs; select a layer after running and inspect its coverage.",
  "architectureTitle": "How does it compute without an analysis backend?",
  "architecture": "GitHub Pages serves static HTML, CSS, JavaScript and public sample files. Your browser executes the downloaded program using your computer's CPU and memory. The main thread manages controls, maps and downloads; a separate Web Worker reads rasters, aligns and reclassifies them, and calculates change and fragmentation before returning arrays. A Web Worker is a browser thread, not a remote server. Uploaded file contents are not sent to a server. Basemap tiles and sample downloads still need the network. Earth Engine and Python prepare public source data before publication. The five numeric modules read prepared values and area weights, then perform map arithmetic, subindicator combination and statistics locally. Upstream satellite composites, climate projections and provider models are not rerun inside the page.",
  "limits": "Current caps: 100 MB and 25 million input pixels per TIFF, 8 million analysis cells, 25 MB per vector file, and 3 periods. Usable size also depends on device memory. Crop or coarsen larger jobs, or use the repository's separate Python command-line engine; the website does not call that engine.",
  "steps": [
    "Static host serves code and samples",
    "Browser Worker computes on your device",
    "Page draws results and creates exports"
  ],
  "how": "How to use",
  "method": "How it works",
  "metrics": "Metric definitions and formulas",
  "entries": [
    {
      "title": "Study-area overview",
      "how": "Use Locate study area to fit the boundary and Regional context to see its surroundings. Overview in the header returns here.",
      "method": "The demo reads the Ganjam GeoJSON. Uploads show the AOI, or the earliest-year GeoTIFF footprint transformed to longitude/latitude. MapLibre draws the outline and fits the view over OpenStreetMap tiles. The selected result is overlaid on this shared map. Use the year selector for land cover and forest, and the layer selector below for numeric diagnostics. Opacity and visibility affect only display."
    },
    {
      "title": "Public example and years",
      "how": "Choose Public data, keep 2002, 2012, 2022 and 50 m, then run both modules. Download the sample TIFFs to try the upload workflow.",
      "method": "GLC-FCS30D is a consistent 30 m product. Earth Engine and Python prepare the cropped 50 m EPSG:6933 inputs with nearest-neighbour sampling. The browser verifies hashes and applies an editable ten-class crosswalk. The source fine classes remain in the input files. Classification errors and resampling mean mapped change still needs local review."
    },
    {
      "title": "Upload rasters, AOI and class inspection",
      "how": "Choose Upload your own GeoTIFFs, enter years and select 1–3 single-band categorical TIFFs. Load raster class codes lists their categories. Optionally add an AOI GeoJSON or one zipped Shapefile; otherwise analysis uses the earliest-year raster extent.",
      "method": "geotiff.js reads pixels and georeferencing; proj4 transforms WGS84, WGS84 UTM, Web Mercator and EPSG:6933. GeoJSON must use WGS84; a Shapefile ZIP needs .shp, .dbf and .prj. Code 0 and declared NoData are excluded. Convert RGB images, rotated grids and PixelIsPoint rasters in GIS first."
    },
    {
      "title": "Diagnostic module",
      "how": "LULC change needs 2–3 distinct years. Forest fragmentation accepts 1–3 years. Running both needs 2–3.",
      "method": "LULC compares adjacent periods plus first-to-last when three years are supplied: three periods yield three comparisons. Fragmentation is calculated independently for each year."
    },
    {
      "title": "Analysis resolution",
      "how": "Grid resolution is in metres. Start at 50 m; use 100 m or coarser for larger areas. Edge width must be at least one analysis cell.",
      "method": "Inputs are aligned by nearest-neighbour sampling to one EPSG:6933 equal-area grid; pixel centres determine AOI membership. Area in hectares = pixel count × cell size² / 10,000. Finer grids need more memory; upsampling the 50 m public inputs does not restore 30 m source detail."
    },
    {
      "title": "Reclassification crosswalk",
      "how": "Expand Reclassify land cover. Source is the original code; Target, Name and Colour define the unified class. Merge sources by giving them the same target code, name and colour, or import a CSV.",
      "method": "After alignment, each pixel is recoded with one shared crosswalk for all years. Every observed source must be mapped. CSV columns: source_code,target_code,target_name,color. Target codes are 1–999; colours use #RRGGBB. Colours alone do not alter area; merging classes changes the analysis."
    },
    {
      "title": "Forest definition",
      "how": "Select target classes in Classes counted as forest. The GLC-FCS30D project legend defaults to Forest including mangroves (2); orchards remain cropland. Review your selection after reclassification.",
      "method": "Selected classes become a binary forest mask; other valid classes are non-forest. This is a user-defined analytical mask. Tree cover is not automatically a national legal definition of forest."
    },
    {
      "title": "Edge width and boundary option",
      "how": "Set Forest edge width, for example 50 or 100 m. Count AOI / NoData boundaries as edges is off by default; enable it to count study-area and missing-data boundaries.",
      "method": "An exact Euclidean distance transform measures pixel-centre distance to the nearest non-forest pixel. Distance strictly greater than the threshold defines candidate core; the remainder is candidate edge. Counting unknown boundaries reduces core near them. Protection boundaries never create forest edges."
    },
    {
      "title": "Protected areas and OECM",
      "how": "Expand Protection & OECM layers and upload either or both polygon datasets. Run a fragmentation module. Use complete coverage for your study area.",
      "method": "Classify the whole landscape first, then summarise Protected, OECM and remainder, with Protected taking precedence. Area is allocated by pixel. NP, MPS, MPE, MSI and AWMSI assign each whole patch to its majority stratum; ties prefer Protected, OECM, then remainder. LPI uses actual intersection area. Remainder only means outside supplied polygons, not legally unprotected."
    },
    {
      "title": "Land-cover and class-difference maps",
      "how": "After a run, choose Land cover for yearly maps or Class difference for pairwise differences, including first-to-last. Hover to inspect pixel classes and use the legend for colours.",
      "method": "Canvas colours the calculated arrays with transparent NoData. Differences use only cells valid in both periods: same class = 0, different = 1. The overview basemap does not enter area or distance calculations."
    },
    {
      "title": "Transition matrix, gains and losses",
      "how": "Choose the comparison period. Rows are earlier classes, columns are later classes, and values are hectares. Diagonal cells retain their class; off-diagonal cells are transitions.",
      "method": "Count from→to pairs within common valid coverage. Gross loss is the off-diagonal row sum; gross gain is the off-diagonal column sum; net = gain − loss. Yearly area tables use each year's own coverage, so their area difference may differ from net change when valid footprints differ."
    },
    {
      "title": "Forest-fragmentation map",
      "how": "Choose Forest fragmentation: green Core, yellow Edge, red Patch (a forest patch without core), purple Internal clearing, neutral Non-forest, and transparent NoData.",
      "method": "Forest components use 8-neighbour connectivity, including diagonals. A component without any core cell becomes Patch; others retain Core and Edge. Non-forest uses 4-neighbour connectivity; components touching the exterior or NoData are not clearings. Core + Edge + Patch equals total forest area; clearings are excluded."
    },
    {
      "title": "Forest metrics",
      "how": "Compare years and strata in Fragmentation by year & protection. Interpret patch counts with core area, resolution and the forest definition; NP alone does not measure ecological quality.",
      "method": "Metrics use connected-component areas and raster-side perimeters. NP counts all connected forest patches, not only the red Patch class. Formulas are below. Raster shape metrics depend on the boundary option; this reference adaptation is not guaranteed to match ArcPy polygon perimeter measurements exactly."
    },
    {
      "title": "Run, stop and export",
      "how": "Use Run with current settings or Run analysis. Pan the map while computing; Stop computation / Cancel analysis ends the run. Results appear below the overview. Changed settings require another run.",
      "method": "GeoTIFF preserves the full grid, CRS and NoData. PNG includes the display legend. CSV exports areas, transitions, gains/losses and forest metrics. Run manifest JSON records hashes, settings, crosswalk, checks and limitations. Downloads are generated locally. Stopping terminates the Worker; closing or refreshing loses in-memory results."
    }
  ]
};
export const metricDefinitions = [
  [
    "landscape_ha",
    "Valid landscape area",
    "Valid cells × cell area (ha)"
  ],
  [
    "forest_ha / PLAND",
    "Forest area / cover",
    "PLAND = forest_ha / landscape_ha × 100%"
  ],
  [
    "core_ha / edge_ha / patch_ha",
    "Core / edge / patch area",
    "The three areas sum to forest_ha"
  ],
  [
    "clearing_ha",
    "Internal clearing area (non-forest)",
    "Excluded from forest_ha"
  ],
  [
    "core_pct",
    "Core share of forest",
    "core_ha / forest_ha × 100%"
  ],
  [
    "NP",
    "Connected forest patch count",
    "All forest components, using 8-neighbour connectivity"
  ],
  [
    "TE_m / ED",
    "Total edge / edge density",
    "ED = TE_m / landscape_ha (m/ha)"
  ],
  [
    "MPS_ha / MPE",
    "Mean patch area / mean perimeter",
    "Sum of whole-patch area (ha) or perimeter (m) / NP"
  ],
  [
    "MSI / AWMSI",
    "Mean / area-weighted shape index",
    "Per-patch shape = 0.25 × perimeter(m) / √area(m²); MSI = mean(shape); AWMSI = Σ(shape × area) / Σarea"
  ],
  [
    "LPI / largest_patch_ha",
    "Largest patch index / area",
    "LPI = largest_patch_ha / landscape_ha × 100%; use actual within-stratum intersection area"
  ],
  [
    "clearings_intersecting",
    "Clearings intersecting the stratum",
    "A clearing may intersect multiple strata; do not add stratum counts"
  ]
];
