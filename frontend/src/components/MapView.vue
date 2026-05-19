<template>
  <div class="center">
    <div ref="mapEl" class="map"></div>
    <div class="chart-strip">
      <div class="chart-hdr">
        <div class="chart-hdr-left">
          <span class="chart-title">{{ chartTitle }}</span>
          <select class="param-select" v-model="chartParam">
            <option value="soc_pct">Заряд (SOC)</option>
            <option value="battery_temp_c">Температура</option>
            <option value="speed_kph">Швидкість</option>
          </select>
        </div>
        <div class="chart-hdr-right">
          <span class="chart-label">{{ selected ? selected : '← оберіть авто' }}</span>
          <button v-if="selected" class="btn-report" @click="$emit('open-report', selected)">⬇ PDF звіт</button>
        </div>
      </div>
      <canvas ref="chartEl"></canvas>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import L from 'leaflet'
import { Chart, LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler } from 'chart.js'

Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler)

const props = defineProps({
  vehicles:     { type: Array,  default: () => [] },
  selected:     { type: String, default: null },
  chartHistory: { type: Array,  default: () => [] },
})
defineEmits(['select', 'open-report'])

const PARAM_CONFIG = {
  soc_pct:        { title: 'ЗАРЯД (SOC)',   unit: '%',      color: '#00e5ff', bg: 'rgba(0,229,255,.08)',   min: 0,  max: 100, fmt: v => v + '%' },
  battery_temp_c: { title: 'ТЕМПЕРАТУРА',   unit: '°C',     color: '#ff9800', bg: 'rgba(255,152,0,.08)',   min: 0,  max: 80,  fmt: v => v + '°C' },
  speed_kph:      { title: 'ШВИДКІСТЬ',     unit: 'км/год', color: '#4caf50', bg: 'rgba(76,175,80,.08)',   min: 0,  max: 120, fmt: v => v + '' },
}

const chartParam = ref('soc_pct')
const chartTitle = computed(() => PARAM_CONFIG[chartParam.value].title + ' — останні 15 хвилин')

const mapEl   = ref(null)
const chartEl = ref(null)

let map        = null
let socChart   = null
let markers    = {}
let routeLines = {}
let markerPositions = {}

onMounted(() => {
  // MAP
  map = L.map(mapEl.value, { zoomControl: false }).setView([50.45, 30.52], 11)
  L.control.zoom({ position: 'bottomright' }).addTo(map)
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '© CartoDB', subdomains: 'abcd', maxZoom: 19,
  }).addTo(map)

  // DEPOT
  L.circle([50.4501, 30.5234], {
    radius: 100, color: '#00e5ff', fillColor: '#00e5ff',
    fillOpacity: 0.08, weight: 1.5, dashArray: '5 5',
  }).addTo(map).bindTooltip('Головне депо', { permanent: true, direction: 'top' })
  L.circleMarker([50.4501, 30.5234], {
    radius: 5, color: '#00e5ff', fillColor: '#00e5ff', fillOpacity: 1, weight: 0,
  }).addTo(map)

  const cfg = PARAM_CONFIG[chartParam.value]
  socChart = new Chart(chartEl.value.getContext('2d'), {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: cfg.title, data: [],
        borderColor: cfg.color, backgroundColor: cfg.bg,
        borderWidth: 2, pointRadius: 2, tension: 0.4, fill: true,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: { duration: 300 },
      plugins: { legend: { display: false } },
      scales: {
        x: {
          ticks: { color: '#4a6070', font: { family: 'Share Tech Mono', size: 9 }, maxTicksLimit: 8 },
          grid:  { color: 'rgba(26,42,58,.8)' },
        },
        y: {
          min: cfg.min, max: cfg.max,
          ticks: { color: '#4a6070', font: { family: 'Share Tech Mono', size: 9 }, callback: cfg.fmt },
          grid:  { color: 'rgba(26,42,58,.8)' },
        },
      },
    },
  })
})

onUnmounted(() => {
  if (map) map.remove()
  if (socChart) socChart.destroy()
})

function statusClass(v) {
  if (v.active_error_code && !['None', '', 'null'].includes(String(v.active_error_code))) return 'error'
  if (v.soc_pct !== null && v.soc_pct < 20) return 'warn'
  if (v.battery_temp_c !== null && v.battery_temp_c > 55) return 'warn'
  return 'ok'
}

watch(() => props.vehicles, (vehicles) => {
  if (!map) return
  const active = vehicles.filter(v => v.timestamp !== null)

  active.forEach(v => {
    const cls = statusClass(v)
    const soc = v.soc_pct != null ? +v.soc_pct.toFixed(1) : null
    const temp = v.battery_temp_c != null ? +v.battery_temp_c.toFixed(1) : null

    if (v.lat && v.lon) {
      const newLat = parseFloat(v.lat)
      const newLon = parseFloat(v.lon)
      const icon = L.divIcon({
        className: '',
        html: `<div class="car-marker ${cls}">🚗</div>`,
        iconSize: [32, 32], iconAnchor: [16, 16],
      })
      const prevPos = markerPositions[v.vehicle_id]
      const hasMoved = !prevPos ||
        Math.abs(prevPos.lat - newLat) > 0.0001 ||
        Math.abs(prevPos.lon - newLon) > 0.0001

      if (markers[v.vehicle_id]) {
        if (hasMoved) {
          markers[v.vehicle_id].setLatLng([newLat, newLon], { animate: true, duration: 1.0 })
          const el = markers[v.vehicle_id].getElement()
          if (el) {
            const inner = el.querySelector('.car-marker')
            if (inner) { inner.classList.add('moving'); setTimeout(() => inner.classList.remove('moving'), 600) }
          }
        }
        markers[v.vehicle_id].setIcon(icon)
      } else {
        const m = L.marker([newLat, newLon], { icon }).addTo(map)
        m.bindPopup(`
          <b style="font-family:monospace">${v.vehicle_id}</b><br>
          ${v.brand} ${v.model}<br>
          SOC: <b>${soc ?? '—'}%</b> | Temp: <b>${temp ?? '—'}°C</b><br>
          ${v.active_error_code && !['None', ''].includes(String(v.active_error_code))
            ? `<span style="color:#ff3d3d">⚠ ${v.active_error_code}</span>` : '✓ Без помилок'}
        `)
        m.on('click', () => props.selected) // emit handled via parent
        markers[v.vehicle_id] = m
      }
      markerPositions[v.vehicle_id] = { lat: newLat, lon: newLon }
    }

    // routes
    fetch(`/api/route/${v.vehicle_id}`)
      .then(r => r.json())
      .then(pts => {
        if (pts.length < 2) return
        const latlngs = pts.map(p => [p.lat, p.lon])
        const color = v.active_error_code && !['None', ''].includes(String(v.active_error_code))
          ? '#ff3d3d' : '#00e5ff'
        if (routeLines[v.vehicle_id]) {
          routeLines[v.vehicle_id].setLatLngs(latlngs)
          routeLines[v.vehicle_id].setStyle({ color })
        } else {
          routeLines[v.vehicle_id] = L.polyline(latlngs, {
            color, weight: 2, opacity: 0.5, dashArray: '4 6',
          }).addTo(map)
        }
      })
  })
}, { deep: true })

function applyChartData(data, param) {
  if (!socChart || !data.length) return
  const cfg = PARAM_CONFIG[param]
  socChart.data.labels = data.map(d => new Date(d.timestamp).toLocaleTimeString('uk-UA'))
  socChart.data.datasets[0].data            = data.map(d => d[param])
  socChart.data.datasets[0].borderColor     = cfg.color
  socChart.data.datasets[0].backgroundColor = cfg.bg
  socChart.options.scales.y.min             = cfg.min
  socChart.options.scales.y.max             = cfg.max
  socChart.options.scales.y.ticks.callback  = cfg.fmt
  socChart.update()
}

watch(() => props.chartHistory, data => applyChartData(data, chartParam.value))
watch(chartParam, param => applyChartData(props.chartHistory, param))
</script>

<style scoped>
.center { display: grid; grid-template-rows: 1fr 180px; overflow: hidden; }
.map    { width: 100%; height: 100%; }

.chart-strip {
  background: var(--panel);
  border-top: 1px solid var(--border);
  padding: 10px 18px;
  display: flex;
  flex-direction: column;
}
.chart-hdr {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;
}
.chart-hdr-left { display: flex; align-items: center; gap: 10px; }
.chart-title { font-family: var(--mono); font-size: .62rem; color: var(--muted); letter-spacing: .1em; }
.chart-hdr-right { display: flex; align-items: center; gap: 10px; }

.param-select {
  font-family: var(--mono);
  font-size: .62rem;
  background: rgba(0,229,255,.06);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--accent);
  padding: 2px 8px;
  cursor: pointer;
  outline: none;
  transition: border-color .2s;
}
.param-select:hover { border-color: var(--accent); }
.param-select option { background: #0d1b2a; }
.chart-label { font-family: var(--mono); font-size: .72rem; color: var(--accent); }

.btn-report {
  font-family: var(--mono); font-size: .65rem;
  padding: 3px 11px; border-radius: 4px; cursor: pointer;
  background: rgba(0,229,255,.08); border: 1px solid var(--accent);
  color: var(--accent); transition: .2s;
}
.btn-report:hover { background: rgba(0,229,255,.2); }

canvas { flex: 1; }
</style>
