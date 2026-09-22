"""Configuration validation shared by local and server preparation."""
import math
import re

MODULES = {
    "groundwater": "Groundwater storage",
    "drought": "Drought & vegetation stress",
    "climate": "Climate extremes",
    "flood": "River flood hazard",
    "degradation": "Land degradation",
}

MODELS = ["ACCESS-CM2", "MIROC6", "MPI-ESM1-2-HR"]

METRICS = ["hot", "warm", "frost", "temperature", "rain", "dry"]

def years(value, label, low, high):
    if not isinstance(value, list) or len(value) != 2 or any(type(v) is not int for v in value):
        raise ValueError(f"{label}: enter a start and end year.")
    if not low <= value[0] <= value[1] <= high:
        raise ValueError(f"{label}: supported years are {low}–{high}.")
    return list(range(value[0], value[1] + 1))

def validate_config(c):
    if c.get("schema") != "nbs-local-job/v1":
        raise ValueError("Unsupported job file. Download a fresh Python package.")
    if not isinstance(c.get("name"), str) or not 1 <= len(c["name"].strip()) <= 120:
        raise ValueError("Enter a study-area name of 1–120 characters.")
    selected = c.get("modules", [])
    if (
        not selected
        or len(selected) != len(set(selected))
        or any(m not in MODULES for m in selected)
    ):
        raise ValueError("Select at least one supported numeric module.")
    if not re.fullmatch(r"[a-f0-9]{64}", c.get("boundarySha256", "")):
        raise ValueError("The job needs its original boundary checksum.")
    g = c["groundwater"]
    years(g["baseline"], "Groundwater baseline", 2003, 2025)
    years(g["monitoring"], "Groundwater monitoring", 2003, 2025)
    if g["baseline"][1] >= g["monitoring"][0]:
        raise ValueError("Groundwater monitoring must follow the baseline.")
    d = c["drought"]
    ref = years(d["reference"], "VHI reference", 2001, 2024)
    if len(ref) < 15 or not 15 <= d["minimumYears"] <= len(ref):
        raise ValueError("VHI needs at least 15 reference years.")
    if len(d["compare"]) != 2 or not ref[0] <= d["compare"][0] < d["compare"][1] <= ref[-1]:
        raise ValueError("Choose two different VHI years inside the reference period.")
    if not 1 <= len(d["seasons"]) <= 2:
        raise ValueError("Choose one or two growing seasons.")
    occupied = set()
    for season in d["seasons"]:
        if not isinstance(season.get("name"), str) or not 1 <= len(season["name"].strip()) <= 50:
            raise ValueError("Each season needs a short name.")
        start, end = season["start"], season["end"]
        if (
            type(start) is not int
            or type(end) is not int
            or not (1 <= start <= 12 and 1 <= end <= 12)
        ):
            raise ValueError("Season months must be 1–12.")
        months = {(start - 1 + i) % 12 + 1 for i in range((end - start) % 12 + 1)}
        if occupied & months:
            raise ValueError("Growing seasons must not overlap.")
        occupied |= months
    k = c["climate"]
    years(k["baseline"], "Climate baseline", 1950, 2020)
    years(k["future"], "Climate future", 2021, 2100)
    for key, allowed in [
        ("models", MODELS),
        ("scenarios", ["ssp245", "ssp585"]),
        ("metrics", METRICS),
    ]:
        if not k[key] or len(k[key]) != len(set(k[key])) or any(v not in allowed for v in k[key]):
            raise ValueError(f"Choose supported climate {key}.")
    for key, limits in {
        "hot": (-20, 60),
        "warm": (-20, 45),
        "rain": (1, 500),
        "dry": (0.1, 20),
    }.items():
        v = k["thresholds"][key]
        if (
            not isinstance(v, (int, float))
            or not math.isfinite(v)
            or not limits[0] <= v <= limits[1]
        ):
            raise ValueError(f"Climate threshold {key} is outside the supported range.")
    if not c["flood"]["returnPeriods"] or any(
        v not in [10, 100, 500] for v in c["flood"]["returnPeriods"]
    ):
        raise ValueError("Supported flood return periods are 10, 100 and 500 years.")
    if c.get("landMask") not in ["worldcover2021", "all-land"]:
        raise ValueError("Choose the WorldCover 2021 mask or explicitly use the full AOI.")
    if not 0.1 <= c.get("maxDownloadGB", 0) <= 100:
        raise ValueError("Download budget must be 0.1–100 GB.")
    return c
