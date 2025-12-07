import os
import glob
import warnings

import numpy as np
import pandas as pd
import xarray as xr
import geopandas as gpd
from shapely.geometry import Point

warnings.filterwarnings("ignore", category=FutureWarning)

BASE_DIR = r"C:\web mapping"
DATA_DIR = os.path.join(BASE_DIR, "data")
VECTOR_DIR = os.path.join(DATA_DIR, "vector")
TEMP_DIR = os.path.join(DATA_DIR, "temperature")

# Fichiers d'entrée
REGIONS_GEOJSON = os.path.join(VECTOR_DIR, "region12Maroc.json")

# Fichier de sortie
OUT_REGIONS_TEMP = os.path.join(VECTOR_DIR, "regions_temp_2024.geojson")

TEMP_VAR_CANDIDATES = ["t2m", "2m_temperature", "t", "temp", "temperature"]


def load_era5_temp():
    pattern = os.path.join(TEMP_DIR, "era5_temperature_2024_*.nc")
    files = sorted(glob.glob(pattern))
    if not files:
        raise RuntimeError(f"Aucun fichier NetCDF trouvé avec le pattern : {pattern}")

    print("Chargement des fichiers NetCDF température...")
    for f in files:
        print(" -", f)

    datasets = []
    time_coord_name = None

    for f in files:
        ds_single = xr.open_dataset(f)

        if "number" in ds_single.dims:
            ds_single = ds_single.isel(number=0)
        if "expver" in ds_single.dims:
            ds_single = ds_single.isel(expver=0)

        if time_coord_name is None:
            if "time" in ds_single.coords:
                time_coord_name = "time"
            elif "valid_time" in ds_single.coords:
                time_coord_name = "valid_time"
            else:
                raise RuntimeError(
                    f"Aucune coordonnée temporelle 'time' ou 'valid_time' trouvée dans {f}"
                )

        datasets.append(ds_single)

    ds = xr.concat(datasets, dim=time_coord_name)

    temp_var = None
    for cand in TEMP_VAR_CANDIDATES:
        if cand in ds.data_vars:
            temp_var = cand
            break
    if temp_var is None:
        raise RuntimeError(
            f"Aucune variable de température trouvée parmi {TEMP_VAR_CANDIDATES}. "
            f"Variables présentes : {list(ds.data_vars)}"
        )

    print(f"Variable de température utilisée : {temp_var}")

    if time_coord_name == "valid_time":
        ds = ds.rename({"valid_time": "time"})
        time_coord_name = "time"

    ds["time"] = pd.to_datetime(ds["time"].values)

    return ds, temp_var


def compute_monthly_temp_c(ds, temp_var):
    print("Calcul des températures mensuelles (°C)...")

    da = ds[temp_var]

    # ERA5 t2m est en Kelvin → °C
    da_c = da - 273.15

    da_monthly = da_c.groupby("time.month").mean("time")
    da_monthly = da_monthly.rename({"month": "month"})
    print("Dimensions mensuelles :", da_monthly.dims)
    return da_monthly


def load_regions():
    print(f"Chargement des régions depuis {REGIONS_GEOJSON} ...")
    gdf = gpd.read_file(REGIONS_GEOJSON)
    print("Colonnes des régions :", gdf.columns)

    gdf["region_id"] = gdf["id"]
    gdf["nom_region"] = gdf["name"]

    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)

    return gdf


def compute_region_stats_temp(da_monthly, gdf_regions):
    print("Calcul des statistiques régionales de température...")

    monthly_series = {}

    for m in range(1, 13):
        print(f"  - Traitement du mois {m} ...")
        da_m = da_monthly.sel(month=m)

        df = da_m.to_dataframe(name="temp_c").reset_index()
        df = df.dropna(subset=["temp_c"])

        geometry = [Point(lon, lat) for lon, lat in zip(df["longitude"], df["latitude"])]
        gdf_points = gpd.GeoDataFrame(df[["temp_c"]], geometry=geometry, crs="EPSG:4326")

        gdf_join = gpd.sjoin(
            gdf_points,
            gdf_regions[["region_id", "nom_region", "geometry"]],
            how="inner",
            predicate="within",
        )

        s = gdf_join.groupby("region_id")["temp_c"].mean()
        monthly_series[m] = s

    gdf_out = gdf_regions.copy()
    for m in range(1, 13):
        col = f"temp_{m:02d}"
        s = monthly_series[m]
        gdf_out[col] = gdf_out["region_id"].map(s)

    return gdf_out


def main():
    ds, temp_var = load_era5_temp()
    da_monthly = compute_monthly_temp_c(ds, temp_var)

    gdf_regions = load_regions()
    gdf_regions_temp = compute_region_stats_temp(da_monthly, gdf_regions)
    print(f"Enregistrement des régions avec température : {OUT_REGIONS_TEMP}")
    gdf_regions_temp.to_file(OUT_REGIONS_TEMP, driver="GeoJSON")

    print("✅ Terminé (température).")


if __name__ == "__main__":
    main()
