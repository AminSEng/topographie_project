import os
import json
from flask import Flask, render_template, jsonify

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
VECTOR_DIR = os.path.join(BASE_DIR, "data", "vector")


print("TEMPLATES_DIR =", TEMPLATES_DIR)
print("STATIC_DIR    =", STATIC_DIR)

# Fichiers précipitations
REGIONS_PRECIP_PATH = os.path.join(VECTOR_DIR, "regions_precip_2024.geojson")
VILLES_PRECIP_PATH  = os.path.join(VECTOR_DIR, "villes_precip_2024.geojson")

# Fichiers température
REGIONS_TEMP_PATH = os.path.join(VECTOR_DIR, "regions_temp_2024.geojson")
VILLES_TEMP_PATH  = os.path.join(VECTOR_DIR, "villes_temp_2024.geojson")  # optionnel

# Mois
MONTH_LABELS = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin",
                "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]

app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)

# --------------------- Chargement des données ----------------------

def safe_load_geojson(path, description=""):
    if os.path.exists(path):
        print(f"Chargement {description} : {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        print(f"⚠️ {description} non trouvé : {path} -> renvoi FeatureCollection vide")
        return {"type": "FeatureCollection", "features": []}

REGIONS_PRECIP_DATA = safe_load_geojson(REGIONS_PRECIP_PATH, "Régions précipitations")
VILLES_PRECIP_DATA  = safe_load_geojson(VILLES_PRECIP_PATH,  "Villes précipitations")

REGIONS_TEMP_DATA = safe_load_geojson(REGIONS_TEMP_PATH, "Régions température")
VILLES_TEMP_DATA  = safe_load_geojson(VILLES_TEMP_PATH,  "Villes température")

# --------------------- ROUTES HTML ----------------------

@app.route("/")
def home():
    # Page menu : Choix Précipitations / Température
    return render_template("home.html")

@app.route("/precip")
def precip_page():
    # Ta page actuelle de précipitations (index.html existant)
    return render_template("index.html")

@app.route("/temp")
def temp_page():
    # Nouvelle page pour la température
    return render_template("temp.html")

# --------------------- ROUTES API COMMUNES ----------------------

@app.route("/api/mois")
def api_mois():
    return jsonify({"labels": MONTH_LABELS})

# ----- API Précipitations -----

@app.route("/api/regions")
def api_regions_precip():
    # Compatibilité avec ton main.js existant (précip)
    return jsonify(REGIONS_PRECIP_DATA)

@app.route("/api/villes")
def api_villes_precip():
    return jsonify(VILLES_PRECIP_DATA)

# ----- API Température -----

@app.route("/api/temp/regions")
def api_regions_temp():
    return jsonify(REGIONS_TEMP_DATA)

@app.route("/api/temp/villes")
def api_villes_temp():
    return jsonify(VILLES_TEMP_DATA)

# --------------------- MAIN ----------------------

if __name__ == "__main__":
    app.run(debug=True)
