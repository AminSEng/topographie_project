let map;
let regionsLayer;
let monthsMeta;
let currentMonth = 1;
let chart;
let globalStats = null;

document.addEventListener("DOMContentLoaded", async () => {
  await initMap();
  initSlider();
  initChart();
  updateLegend();
});

async function initMap() {
  map = L.map("map").setView([31.5, -6.5], 5);

  L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    { attribution: "Tiles © Esri" }
  ).addTo(map);

  monthsMeta = await (await fetch("/api/mois")).json();

  const regionsData = await (await fetch("/api/temp/regions")).json();

  globalStats = calcGlobalMinMax(regionsData);

  regionsLayer = L.geoJSON(regionsData, {
    style: feature => regionStyle(feature),
    onEachFeature: (feature, layer) => {
      layer.on("click", () => onRegionClick(feature));
      layer.bindTooltip(feature.properties.nom_region || "Région");
    }
  }).addTo(map);
}

function initSlider() {
  const slider = document.getElementById("monthRange");
  const label  = document.getElementById("monthLabel");

  slider.addEventListener("input", () => {
    currentMonth = parseInt(slider.value);
    label.textContent = monthsMeta.labels[currentMonth - 1];
    regionsLayer.setStyle(feature => regionStyle(feature));
    updateLegend();
  });

  label.textContent = monthsMeta.labels[currentMonth - 1];
}

function regionStyle(feature) {
  const value = getRegionValue(feature, currentMonth);
  const color = getColorTemp(value, globalStats.min, globalStats.max);

  return {
    fillColor: color,
    color: "#555",
    weight: 1,
    fillOpacity: 0.7
  };
}

function getMonthPropertyName(month) {
  return `temp_${String(month).padStart(2, "0")}`;
}

function getRegionValue(feature, month) {
  const prop = getMonthPropertyName(month);
  return feature.properties[prop];
}

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

// Dégradé bleu -> rouge pour températures
function getColorTemp(v, min, max) {
  if (v === null || v === undefined || isNaN(v)) return "#f0f0f0";

  const t = (v - min) / (max - min || 1);
  const s = Math.max(0, Math.min(1, t));

  const r = Math.round(255 * s);
  const g = Math.round(255 * (1 - Math.abs(s - 0.5) * 2));
  const b = Math.round(255 * (1 - s));
  return `rgb(${r},${g},${b})`;
}

function updateLegend() {
  if (!globalStats) return;
  const { min, max } = globalStats;

  const legendDiv = document.getElementById("legend-scale");
  legendDiv.innerHTML = "";

  const steps = 5;
  for (let i = 0; i <= steps; i++) {
    const v = min + (i / steps) * (max - min);
    const color = getColorTemp(v, min, max);

    const item = document.createElement("div");
    item.className = "legend-item";

    const colorDiv = document.createElement("div");
    colorDiv.className = "legend-color";
    colorDiv.style.background = color;

    const label = document.createElement("div");
    label.textContent = v.toFixed(1);

    item.appendChild(colorDiv);
    item.appendChild(label);
    legendDiv.appendChild(item);
  }
}

function initChart() {
  const ctx = document.getElementById("chart").getContext("2d");
  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: monthsMeta.labels,
      datasets: [{
        label: "Température (°C)",
        data: [],
        fill: true,
        tension: 0.3
      }]
    },
    options: {
      responsive: true,
      scales: {
        y: {
          title: { display: true, text: "°C" }
        }
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

function onRegionClick(feature) {
  const props = feature.properties;
  const title = props.nom_region || "Région";
  const data = getMonthlySeries(props);

  document.getElementById("info-title").textContent = title;
  document.getElementById("info-subtitle").textContent =
    "Température moyenne mensuelle (°C)";
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
