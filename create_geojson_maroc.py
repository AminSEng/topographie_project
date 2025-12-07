# create_geojson_maroc.py

import os
import geopandas as gpd
from shapely.geometry import Point

# Chemin de base de ton projet
BASE_DIR = r"C:\web mapping"
VECTOR_DIR = os.path.join(BASE_DIR, "data", "vector")

# Fichier GADM niveau 1 (régions)
GADM_LEVEL1_SHP = os.path.join(VECTOR_DIR, "gadm41_MAR_1.shp")

# Fichiers de sortie
REGIONS_OUT = os.path.join(VECTOR_DIR, "regions_maroc.geojson")
VILLES_OUT = os.path.join(VECTOR_DIR, "villes_maroc.geojson")


# ------------- 1. CRÉATION DES RÉGIONS ------------- #

def create_regions_geojson():
    print("Chargement du shapefile GADM niveau 1...")
    gdf = gpd.read_file(GADM_LEVEL1_SHP)

    # On vérifie si les colonnes attendues existent
    print("Colonnes disponibles :", gdf.columns)

    # GADM v4.1 : généralement les colonnes importantes sont :
    # 'GID_1', 'NAME_1', 'CC_1', etc.
    if "GID_1" not in gdf.columns or "NAME_1" not in gdf.columns:
        raise ValueError("Le shapefile GADM ne contient pas les colonnes GID_1 / NAME_1.")

    # On garde uniquement ce qui nous intéresse
    gdf_regions = gdf[["GID_1", "NAME_1", "geometry"]].copy()

    # Renommer les colonnes pour ton projet
    gdf_regions = gdf_regions.rename(columns={
        "GID_1": "id_region",
        "NAME_1": "nom_region"
    })

    # S'assurer du CRS WGS84
    if gdf_regions.crs is None:
        gdf_regions = gdf_regions.set_crs("EPSG:4326")
    else:
        gdf_regions = gdf_regions.to_crs("EPSG:4326")

    # Export en GeoJSON
    gdf_regions.to_file(REGIONS_OUT, driver="GeoJSON", encoding="utf-8")
    print(f"Fichier régions créé : {REGIONS_OUT}")


# ------------- 2. CRÉATION DES VILLES ------------- #
# On crée une liste de grandes villes marocaines avec coordonnées (approx.)

def create_villes_geojson():
    print("Création des points de villes...")

    villes = [
        # id_ville, nom_ville, lon, lat
        (1,  "Rabat",              -6.841650, 34.020882),
        (2,  "Salé",               -6.798460, 34.053103),
        (3,  "Casablanca",         -7.589843, 33.573110),
        (4,  "Fès",                -5.007845, 34.018124),
        (5,  "Meknès",             -5.547271, 33.892166),
        (6,  "Tanger",             -5.833954, 35.759465),
        (7,  "Tétouan",            -5.368377, 35.578453),
        (8,  "Oujda",              -1.908583, 34.681389),
        (9,  "Nador",              -2.933650, 35.168780),
        (10, "Agadir",             -9.598107, 30.427755),
        (11, "Marrakech",          -7.981084, 31.629472),
        (12, "Béni Mellal",       -6.349830, 32.337250),
        (13, "Settat",             -7.620000, 33.000000),
        (14, "El Jadida",          -8.498600, 33.231600),
        (15, "Safi",               -9.237180, 32.299390),
        (16, "Errachidia",         -4.426600, 31.934600),
        (17, "Ouarzazate",         -6.902000, 30.918900),
        (18, "Guelmim",            -10.057400, 28.987000),
        (19, "Laâyoune",           -13.203333, 27.153611),
        (20, "Dakhla",             -15.957976, 23.684774)
    ]

    records = []
    geometries = []

    for vid, name, lon, lat in villes:
        records.append({
            "id_ville": vid,
            "nom_ville": name
        })
        geometries.append(Point(lon, lat))

    gdf_villes = gpd.GeoDataFrame(records, geometry=geometries, crs="EPSG:4326")

    # Export en GeoJSON
    gdf_villes.to_file(VILLES_OUT, driver="GeoJSON", encoding="utf-8")
    print(f"Fichier villes créé : {VILLES_OUT}")


if __name__ == "__main__":
    create_regions_geojson()
    create_villes_geojson()
    print("Tous les GeoJSON ont été créés avec succès.")
