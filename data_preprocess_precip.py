import os
import glob
import warnings

import numpy as np
import pandas as pd
import xarray as xr
import geopandas as gpd
from shapely.geometry import Point

warnings.filterwarnings("ignore", category=FutureWarning)

# ================== CONFIGURATION GÉNÉRALE ==================

BASE_DIR = r"C:\web mapping"
DATA_DIR = os.path.join(BASE_DIR, "data")
VECTOR_DIR = os.path.join(DATA_DIR, "vector")
PRECIP_DIR = os.path.join(DATA_DIR, "precipitation")

# Fichiers d'entrée
REGIONS_GEOJSON = os.path.join(VECTOR_DIR, "region12Maroc.json")   # 12 régions correctes
VILLES_SOURCE_GEOJSON = os.path.join(VECTOR_DIR, "villes_maroc.geojson")  # si disponible

# Fichiers de sortie
OUT_REGIONS_PRECIP = os.path.join(VECTOR_DIR, "regions_precip_2024.geojson")
OUT_VILLES_PRECIP = os.path.join(VECTOR_DIR, "villes_precip_2024.geojson")

# Nom de la variable de précipitation possible dans ERA5
PRECIP_VAR_CANDIDATES = ["tp", "total_precipitation", "precip", "precipitation"]


# ================== 1. CHARGEMENT ERA5 ==================

def load_era5_precip():
    """
    Charge tous les fichiers NetCDF mensuels ERA5 de 2024
    SANS utiliser dask (pas de open_mfdataset),
    puis les concatène manuellement avec xarray.concat.
    """
    pattern = os.path.join(PRECIP_DIR, "era5_precipitation_2024_*.nc")
    files = sorted(glob.glob(pattern))
    if not files:
        raise RuntimeError(f"Aucun fichier NetCDF trouvé avec le pattern : {pattern}")

    print("Chargement des fichiers NetCDF ERA5 (sans dask)...")
    for f in files:
        print(" -", f)

    datasets = []
    time_coord_name = None

    for f in files:
        ds_single = xr.open_dataset(f)

        # enlever les dims inutiles si présentes
        if "number" in ds_single.dims:
            ds_single = ds_single.isel(number=0)
        if "expver" in ds_single.dims:
            ds_single = ds_single.isel(expver=0)

        # détecter le nom de la coordonnée temporelle
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

    # Concaténation explicite le long de la coordonnée temporelle
    ds = xr.concat(datasets, dim=time_coord_name)

    # Trouver la variable de précipitation
    precip_var = None
    for cand in PRECIP_VAR_CANDIDATES:
        if cand in ds.data_vars:
            precip_var = cand
            break
    if precip_var is None:
        raise RuntimeError(
            f"Aucune variable de précipitation trouvée parmi {PRECIP_VAR_CANDIDATES}. "
            f"Variables présentes : {list(ds.data_vars)}"
        )

    print(f"Variable de précipitation utilisée : {precip_var}")

    # Normaliser la coordonnée temporelle en 'time'
    if time_coord_name == "valid_time":
        ds = ds.rename({"valid_time": "time"})
        time_coord_name = "time"

    ds["time"] = pd.to_datetime(ds["time"].values)

    return ds, precip_var



def compute_monthly_precip_mm(ds, precip_var):
    """
    Calcule la précipitation mensuelle (mm) pour 2024
    à partir du Dataset ERA5.
    """
    print("Calcul des précipitations mensuelles (mm)...")

    # 'tp' est souvent en m → conversion en mm
    da = ds[precip_var] * 1000.0  # m → mm

    # GroupBy par mois de 'time' et somme (cumul mensuel)
    da_monthly = da.groupby("time.month").sum("time")

    # On s'assure que la dimension s'appelle bien 'month'
    da_monthly = da_monthly.rename({"month": "month"})

    print("Dimensions mensuelles :", da_monthly.dims)
    return da_monthly  # dims : month, latitude, longitude


# ================== 2. TRAITEMENT RÉGIONS ==================

def load_regions():
    """
    Charge les régions à partir de region12Maroc.json
    et crée les champs region_id / nom_region.
    """
    print(f"Chargement des régions depuis {REGIONS_GEOJSON} ...")
    gdf = gpd.read_file(REGIONS_GEOJSON)
    print("Colonnes des régions :", gdf.columns)

    # On standardise les noms de champs utilisés plus tard
    gdf["region_id"] = gdf["id"]
    gdf["nom_region"] = gdf["name"]

    # S'assurer que CRS = WGS84
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)

    return gdf


def compute_region_stats(da_monthly, gdf_regions):
    """
    Pour chaque mois, calcule la moyenne de précipitation
    pour chaque région en utilisant les centres de grille ERA5.
    """
    print("Calcul des statistiques régionales...")

    # On récupère les coordonnées
    lat_values = da_monthly.coords["latitude"].values
    lon_values = da_monthly.coords["longitude"].values

    # Stockage des séries (une série par mois)
    monthly_series = {}

    for m in range(1, 13):
        print(f"  - Traitement du mois {m} ...")

        da_m = da_monthly.sel(month=m)  # 2D : lat x lon

        df = da_m.to_dataframe(name="precip_mm").reset_index()
        df = df.dropna(subset=["precip_mm"])

        # Création de points
        geometry = [Point(lon, lat) for lon, lat in zip(df["longitude"], df["latitude"])]
        gdf_points = gpd.GeoDataFrame(df[["precip_mm"]], geometry=geometry, crs="EPSG:4326")

        # Jointure spatiale : chaque point → région
        gdf_join = gpd.sjoin(gdf_points, gdf_regions[["region_id", "nom_region", "geometry"]],
                             how="inner", predicate="within")

        # Moyenne par région_id
        s = gdf_join.groupby("region_id")["precip_mm"].mean()
        monthly_series[m] = s

    # Construire GeoDataFrame final
    gdf_out = gdf_regions.copy()
    for m in range(1, 13):
        col = f"precip_{m:02d}"
        s = monthly_series[m]
        gdf_out[col] = gdf_out["region_id"].map(s)

    return gdf_out


# ================== 3. TRAITEMENT VILLES ==================

def load_villes():
    """
    Charge les villes si le fichier existe.
    """
    if not os.path.exists(VILLES_SOURCE_GEOJSON):
        print(f"⚠️ Fichier villes non trouvé : {VILLES_SOURCE_GEOJSON}")
        return None

    print(f"Chargement des villes depuis {VILLES_SOURCE_GEOJSON} ...")
    gdf = gpd.read_file(VILLES_SOURCE_GEOJSON)
    print("Colonnes des villes :", gdf.columns)

    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)

    # On suppose des champs id_ville et nom_ville ou similaires
    if "id_ville" not in gdf.columns:
        gdf["id_ville"] = gdf.index.astype(int)

    if "nom_ville" not in gdf.columns:
        # Si pas de nom, on laisse un ID comme nom
        gdf["nom_ville"] = gdf["id_ville"].astype(str)

    return gdf


def compute_city_stats(da_monthly, gdf_villes):
    """
    Pour chaque ville (point), on extrait la valeur de précipitation
    du pixel ERA5 le plus proche pour chaque mois.
    """
    print("Extraction des précipitations pour chaque ville...")

    lats = da_monthly.coords["latitude"].values
    lons = da_monthly.coords["longitude"].values

    records = []

    for idx, row in gdf_villes.iterrows():
        pt = row.geometry
        if pt is None or pt.is_empty:
            continue

        lat = pt.y
        lon = pt.x

        rec = {
            "id_ville": row["id_ville"],
            "nom_ville": row["nom_ville"],
            "geometry": pt
        }

        # Pour chaque mois, on prend le point de grille le plus proche
        for m in range(1, 13):
            da_m = da_monthly.sel(month=m)
            val = da_m.sel(latitude=lat, longitude=lon, method="nearest").values.item()
            rec[f"precip_{m:02d}"] = float(val)

        records.append(rec)

    gdf_out = gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")
    return gdf_out


# ================== 4. MAIN ==================

def main():
    # 1. Charger ERA5
    ds, precip_var = load_era5_precip()

    # 2. Calculer précip mensuelles (mm)
    da_monthly = compute_monthly_precip_mm(ds, precip_var)

    # 3. Régions
    gdf_regions = load_regions()
    gdf_regions_precip = compute_region_stats(da_monthly, gdf_regions)
    print(f"Enregistrement des régions avec précipitations : {OUT_REGIONS_PRECIP}")
    gdf_regions_precip.to_file(OUT_REGIONS_PRECIP, driver="GeoJSON")

    # 4. Villes (optionnel)
    gdf_villes_source = load_villes()
    if gdf_villes_source is not None:
        gdf_villes_precip = compute_city_stats(da_monthly, gdf_villes_source)
        print(f"Enregistrement des villes avec précipitations : {OUT_VILLES_PRECIP}")
        gdf_villes_precip.to_file(OUT_VILLES_PRECIP, driver="GeoJSON")
    else:
        print("Pas de fichier de villes, on ignore cette étape.")

    print("✅ Terminé avec succès.")


if __name__ == "__main__":
    main()
