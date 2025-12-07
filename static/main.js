let map;
let regionsLayer;
let villesLayer;
let monthsMeta;
let currentMonth = 1;
let chart;
let globalStats = null; // min/max globales

document.addEventListener("DOMContentLoaded", async () => {
  await initMap();
  initSlider();
  initChart();
  updateLegend();
});

// ----------------------
// 1. Initialisation carte
// ----------------------
async function initMap() {
  map = L.map("map").setView([31.5, -6.5], 5);

  L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    {
      attribution: "Tiles © Esri"
    }
  ).addTo(map);

  // Métadonnées mois
  monthsMeta = await (await fetch("/api/mois")).json();

  // Données régions / villes
  const regionsData = await (await fetch("/api/regions")).json();
  const villesData  = await (await fetch("/api/villes")).json();

  // Calcul min/max globales sur toutes les régions et tous les mois
  globalStats = calcGlobalMinMax(regionsData);

  // Couche régions
  regionsLayer = L.geoJSON(regionsData, {
    style: feature => regionStyle(feature),
    onEachFeature: (feature, layer) => {
      layer.on("click", () => onRegionClick(feature));
      layer.bindTooltip(feature.properties.nom_region || "Région");
    }
  }).addTo(map);

  // Couche villes
  villesLayer = L.geoJSON(villesData, {
    pointToLayer: (feature, latlng) => {
      return L.circleMarker(latlng, {
        radius: 4,
        fillColor: "#000",
        color: "#fff",
        weight: 1,
        fillOpacity: 0.9
      });
    },
    onEachFeature: (feature, layer) => {
      layer.on("click", () => onVilleClick(feature));
      layer.bindTooltip(feature.properties.nom_ville || "Ville");
    }
  }).addTo(map);
}

// ----------------------
// 2. Slider temporel
// ----------------------
function initSlider() {
  const slider = document.getElementById("monthRange");
  const label  = document.getElementById("monthLabel");

  slider.addEventListener("input", () => {
    currentMonth = parseInt(slider.value);
    label.textContent = monthsMeta.labels[currentMonth - 1];

    // Mettre à jour le style des régions
    regionsLayer.setStyle(feature => regionStyle(feature));
    updateLegend();
  });

  // Label initial
  label.textContent = monthsMeta.labels[currentMonth - 1];
}

// ----------------------
// 3. Style choroplèthe
// ----------------------
function regionStyle(feature) {
  const value = getRegionValue(feature, currentMonth);
  const color = getColor(value, globalStats.min, globalStats.max);

  return {
    fillColor: color,
    color: "#555555",
    weight: 1,
    fillOpacity: 0.7
  };
}

function getMonthPropertyName(month) {
  return `precip_${String(month).padStart(2, "0")}`;
}

function getRegionValue(feature, month) {
  const prop = getMonthPropertyName(month);
  return feature.properties[prop];
}

// Calcul min/max global sur toutes les régions et tous les mois
function calcGlobalMinMax(geojson) {
  let vals = [];

  geojson.features.forEach(f => {
    for (let m = 1; m <= 12; m++) {
      const v = getRegionValue(f, m);
      if (v !== null && v !== undefined && !isNaN(v)) {
        vals.push(Number(v));
      }
    }
  });

  const min = Math.min(...vals);
  const max = Math.max(...vals);
  return { min, max };
}

function getColor(v, min, max) {
  if (v === null || v === undefined || isNaN(v)) return "#f0f0f0";

  const t = (v - min) / (max - min || 1); // 0..1
  const s = Math.max(0, Math.min(1, t));

  // dégradé bleu
  const r = Math.round(255 * (1 - s));
  const g = Math.round(255 * (1 - s));
  const b = 255;

  return `rgb(${r},${g},${b})`;
}

// ----------------------
// 4. Légende dynamique
// ----------------------
function updateLegend() {
  if (!globalStats) return;
  const { min, max } = globalStats;

  const legendDiv = document.getElementById("legend-scale");
  legendDiv.innerHTML = "";

  const steps = 5;
  for (let i = 0; i <= steps; i++) {
    const v = min + (i / steps) * (max - min);
    const color = getColor(v, min, max);

    const item = document.createElement("div");
    item.className = "legend-item";

    const colorDiv = document.createElement("div");
    colorDiv.className = "legend-color";
    colorDiv.style.background = color;

    const label = document.createElement("div");
    label.textContent = v.toFixed(0);

    item.appendChild(colorDiv);
    item.appendChild(label);
    legendDiv.appendChild(item);
  }
}

// ----------------------
// 5. Graphique (Chart.js)
// ----------------------
function initChart() {
  const ctx = document.getElementById("chart").getContext("2d");
  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: monthsMeta.labels,
      datasets: [{
        label: "Précipitations (mm)",
        data: [],
        fill: true,
        tension: 0.3
      }]
    },
    options: {
      responsive: true,
      scales: {
        y: { title: { display: true, text: "mm" } }
      }
    }
  });
}

function updateChart(title, data) {
  if (!chart) return;
  chart.data.datasets[0].data = data;
  chart.data.datasets[0].label = title;
  chart.update();
}

// ----------------------
// 6. Clic sur région / ville
// ----------------------
function onRegionClick(feature) {
  const props = feature.properties;
  const title = props.nom_region || "Région";
  const data = getMonthlySeries(props);

  document.getElementById("info-title").textContent = title;
  document.getElementById("info-subtitle").textContent =
    "Précipitations mensuelles (mm)";
  updateChart(title, data);
}

function onVilleClick(feature) {
  const props = feature.properties;
  const title = props.nom_ville || "Ville";
  const data = getMonthlySeries(props);

  document.getElementById("info-title").textContent = title;
  document.getElementById("info-subtitle").textContent =
    "Précipitations mensuelles (mm)";
  updateChart(title, data);
}

function getMonthlySeries(props) {
  const arr = [];
  for (let m = 1; m <= 12; m++) {
    const key = getMonthPropertyName(m);
    arr.push(props[key] ?? null);
  }
  return arr;
}
