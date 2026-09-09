from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from rasterio.enums import Resampling  # noqa: E402

from nbs_gis.crosswalk import Crosswalk  # noqa: E402


@dataclass(frozen=True)
class RasterPreview:
    values: np.ndarray
    nodata: int | float | None
    extent: tuple[float, float, float, float]
    crs_label: str


def _read_preview(path: Path, max_dimension: int = 1_800) -> RasterPreview:
    with rasterio.open(path) as source:
        scale = max(source.width, source.height) / max_dimension
        if scale > 1:
            width = max(1, round(source.width / scale))
            height = max(1, round(source.height / scale))
            values = source.read(1, out_shape=(height, width), resampling=Resampling.nearest)
        else:
            values = source.read(1)
        return RasterPreview(
            values=values,
            nodata=source.nodata,
            extent=(
                source.bounds.left,
                source.bounds.right,
                source.bounds.bottom,
                source.bounds.top,
            ),
            crs_label=source.crs.to_string() if source.crs else "CRS unavailable",
        )


def _map_layout(title: str, legend_items: int) -> tuple[Figure, Axes, Axes]:
    legend_rows = max(1, math.ceil(legend_items / 4))
    figure = plt.figure(figsize=(10, 8), constrained_layout=True)
    layout = figure.add_gridspec(2, 1, height_ratios=(10, 0.75 + 0.45 * legend_rows))
    axis = figure.add_subplot(layout[0])
    footer = figure.add_subplot(layout[1])
    axis.set_title(title, fontsize=15, pad=14)
    axis.set_axis_off()
    footer.set_axis_off()
    return figure, axis, footer


def _add_north_arrow(axis: Axes) -> None:
    axis.annotate(
        "N",
        xy=(0.96, 0.96),
        xytext=(0.96, 0.84),
        xycoords="axes fraction",
        textcoords="axes fraction",
        ha="center",
        va="center",
        fontsize=10,
        fontweight="bold",
        arrowprops={"arrowstyle": "-|>", "color": "#1f2933", "linewidth": 1.4},
        bbox={
            "boxstyle": "round,pad=0.18",
            "facecolor": "white",
            "alpha": 0.8,
            "edgecolor": "none",
        },
    )


def write_lulc_map(
    raster_path: Path,
    output_path: Path,
    year: int,
    project_name: str,
    crosswalk: Crosswalk,
    dpi: int,
) -> None:
    preview = _read_preview(raster_path)
    values = preview.values
    classes = [
        target
        for code, target in sorted(crosswalk.target_classes.items())
        if np.any(values == code)
    ]
    display = np.full(values.shape, np.nan, dtype=np.float32)
    for index, target in enumerate(classes):
        display[values == target.code] = index
    if preview.nodata is not None:
        display[values == preview.nodata] = np.nan

    colors = [target.color for target in classes] or ["#cccccc"]
    cmap = ListedColormap(colors).with_extremes(bad=(0, 0, 0, 0))
    figure, axis, footer = _map_layout(
        f"{project_name}\nLand use and land cover {year}", len(classes)
    )
    axis.imshow(
        display,
        cmap=cmap,
        interpolation="nearest",
        extent=preview.extent,
        origin="upper",
    )
    axis.set_aspect("equal")
    _add_north_arrow(axis)
    if classes:
        footer.legend(
            handles=[Patch(facecolor=item.color, label=item.name) for item in classes],
            loc="upper center",
            bbox_to_anchor=(0.5, 1),
            frameon=False,
            fontsize=9,
            ncol=min(4, len(classes)),
        )
    footer.text(
        0.5,
        0.02,
        f"Classified analysis layer · {preview.crs_label} · see run manifest for sources",
        ha="center",
        va="bottom",
        fontsize=8,
        transform=footer.transAxes,
    )
    figure.savefig(output_path, dpi=dpi, facecolor="white")
    plt.close(figure)


def write_change_map(
    raster_path: Path,
    output_path: Path,
    start_year: int,
    end_year: int,
    project_name: str,
    dpi: int,
) -> None:
    preview = _read_preview(raster_path)
    values = preview.values
    display = values.astype(np.float32)
    if preview.nodata is not None:
        display[values == preview.nodata] = np.nan
    cmap = ListedColormap(["#d8e5d7", "#d0693c"]).with_extremes(bad=(0, 0, 0, 0))
    figure, axis, footer = _map_layout(
        f"{project_name}\nLand-cover change {start_year}-{end_year}", 2
    )
    axis.imshow(
        display,
        cmap=cmap,
        vmin=0,
        vmax=1,
        interpolation="nearest",
        extent=preview.extent,
        origin="upper",
    )
    axis.set_aspect("equal")
    _add_north_arrow(axis)
    footer.legend(
        handles=[
            Patch(facecolor="#d8e5d7", label="Stable"),
            Patch(facecolor="#d0693c", label="Changed"),
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, 1),
        frameon=False,
        fontsize=9,
        ncol=2,
    )
    footer.text(
        0.5,
        0.02,
        f"Binary change layer · {preview.crs_label} · see transition tables for classes",
        ha="center",
        va="bottom",
        fontsize=8,
        transform=footer.transAxes,
    )
    figure.savefig(output_path, dpi=dpi, facecolor="white")
    plt.close(figure)
