<template>
  <AppHeader />

  <div class="workspace">
    <!-- LEFT SIDEBAR -->
    <aside class="sidebar sidebar-left">
      <div class="s-section">
        <div class="s-title">Стан флоту</div>
        <div class="stats-row">
          <div class="stat-box">
            <div class="stat-val">{{ activeCount }}</div>
            <div class="stat-lbl">Всього авто</div>
          </div>
          <div class="stat-box">
            <div class="stat-val" style="color:var(--red)">{{ errorCount }}</div>
            <div class="stat-lbl">Помилки</div>
          </div>
        </div>
      </div>

      <div class="s-section grow">
        <div class="s-title">Автомобілі</div>
        <VehicleList :vehicles="fleet" :selected="selectedVehicle" @select="selectVehicle" @detail="openDetail" />
      </div>

      <div class="s-section" style="max-height:180px;display:flex;flex-direction:column;">
        <div class="s-title">⚠ Активні помилки</div>
        <AlertList :alerts="alerts" @ask-ai="openChat" />
      </div>

      <div class="s-section" style="max-height:180px;display:flex;flex-direction:column;">
        <div class="s-title">📍 Моніторинг зони депо</div>
        <GeofenceList :events="geofenceEvents" />
      </div>
    </aside>

    <!-- CENTER -->
    <MapView
      :vehicles="fleet"
      :selected="selectedVehicle"
      :chart-history="chartHistory"
      @select="selectVehicle"
      @open-report="openReport"
    />

    <!-- RIGHT SIDEBAR -->
    <aside class="sidebar sidebar-right">
      <div class="s-section" style="flex:0 0 auto;">
        <div class="s-title">❤ Здоров'я автопарку</div>
        <FleetHealth :health="fleetHealth" />
      </div>
      <div class="s-section" style="flex:0 0 auto;max-height:26%;display:flex;flex-direction:column;">
        <div class="s-title">🔮 Прогноз заряду — через 1 годину</div>
        <PredictionList :predictions="predictions" />
      </div>
      <div class="s-section grow">
        <div class="s-title">📋 Рекомендації</div>
        <RecommendationList :recommendations="recommendations" />
      </div>
    </aside>
  </div>

  <ChatOverlay
    :visible="chatVisible"
    :vehicle-id="chatVehicleId"
    :dtc-code="chatDtcCode"
    @close="chatVisible = false"
  />

  <VehicleDetailModal
    :visible="detailVisible"
    :vehicle="fleet.find(v => v.vehicle_id === detailVehicleId) || {}"
    :prediction="predictions.find(p => p.vehicle_id === detailVehicleId) || null"
    @close="detailVisible = false"
  />
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import AppHeader from './components/AppHeader.vue'
import VehicleList from './components/VehicleList.vue'
import AlertList from './components/AlertList.vue'
import GeofenceList from './components/GeofenceList.vue'
import MapView from './components/MapView.vue'
import PredictionList from './components/PredictionList.vue'
import RecommendationList from './components/RecommendationList.vue'
import ChatOverlay from './components/ChatOverlay.vue'
import FleetHealth from './components/FleetHealth.vue'
import VehicleDetailModal from './components/VehicleDetailModal.vue'

const fleet           = ref([])
const alerts          = ref([])
const predictions     = ref([])
const geofenceEvents  = ref([])
const recommendations = ref([])
const fleetHealth     = ref({ fleet_score: 0, vehicles: [] })
const chartHistory    = ref([])
const selectedVehicle = ref(null)

const chatVisible   = ref(false)
const chatVehicleId = ref('')
const chatDtcCode   = ref('')

const detailVisible   = ref(false)
const detailVehicleId = ref(null)

const activeCount = computed(() => fleet.value.filter(v => v.timestamp !== null).length)
const errorCount  = computed(() => alerts.value.filter(a => a.is_active).length)

async function refresh() {
  try {
    const [f, a, p, g, r, fh] = await Promise.all([
      fetch('/api/fleet').then(r => r.json()),
      fetch('/api/alerts').then(r => r.json()),
      fetch('/api/predictions').then(r => r.json()),
      fetch('/api/geofence/events').then(r => r.json()),
      fetch('/api/recommendations/combined').then(r => r.json()),
      fetch('/api/fleet_health').then(r => r.json()),
    ])
    fleet.value           = f
    alerts.value          = a
    predictions.value     = p
    geofenceEvents.value  = g
    recommendations.value = r
    fleetHealth.value     = fh

    if (selectedVehicle.value) loadChart(selectedVehicle.value)
  } catch (e) {
    console.error(e)
  }
}

async function loadChart(vid) {
  const data = await fetch(`/api/chart/${vid}`).then(r => r.json())
  chartHistory.value = data
}

function selectVehicle(vid) {
  selectedVehicle.value = vid
  loadChart(vid)
}

function openChat(vehicleId, dtcCode) {
  chatVehicleId.value = vehicleId
  chatDtcCode.value   = dtcCode
  chatVisible.value   = true
}

function openReport(vid) {
  window.open(`/api/report/${vid}`, '_blank')
}

function openDetail(vid) {
  detailVehicleId.value = vid
  detailVisible.value   = true
}

let timer
onMounted(() => {
  refresh()
  timer = setInterval(refresh, 5000)
})
onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
.workspace {
  display: grid;
  grid-template-columns: 300px 1fr 320px;
  overflow: hidden;
}
.sidebar {
  background: var(--panel);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.sidebar-left  { border-right: 1px solid var(--border); }
.sidebar-right { border-left:  1px solid var(--border); }

.stats-row { display: grid; grid-template-columns: repeat(2,1fr); gap: 6px; }
.stat-box {
  background: rgba(0,229,255,.04);
  border: 1px solid var(--border);
  border-radius: 6px; padding: 7px; text-align: center;
}
.stat-val { font-family: var(--mono); font-size: 1.3rem; color: var(--accent); line-height: 1; }
.stat-lbl { font-size: .58rem; color: var(--muted); margin-top: 3px; }
</style>
