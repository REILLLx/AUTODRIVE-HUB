<template>
  <AppHeader />

  <div class="workspace">
    <!-- LEFT SIDEBAR -->
    <aside class="sidebar sidebar-left">
      <div class="s-section">
        <div class="s-title">Стан парку РТЗ</div>
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
      <div class="s-section" :class="{ collapsed: rCollapsed.health }" style="flex:0 0 auto;">
        <div class="s-title">
          ❤ Здоров'я парку РТЗ
          <button class="collapse-btn" @click="rCollapsed.health = !rCollapsed.health">{{ rCollapsed.health ? '▸' : '▾' }}</button>
        </div>
        <FleetHealth v-show="!rCollapsed.health" :health="fleetHealth" />
      </div>
      <div class="s-section" :class="{ collapsed: rCollapsed.pred }" style="flex:0 0 auto;max-height:26%;display:flex;flex-direction:column;">
        <div class="s-title">
          🔮 Прогноз заряду — через 1 годину
          <button class="collapse-btn" @click="rCollapsed.pred = !rCollapsed.pred">{{ rCollapsed.pred ? '▸' : '▾' }}</button>
        </div>
        <PredictionList v-show="!rCollapsed.pred" :predictions="predictions" />
      </div>
      <div class="s-section grow" :class="{ collapsed: rCollapsed.recs }">
        <div class="s-title">
          📋 Рекомендації
          <button class="collapse-btn" @click="rCollapsed.recs = !rCollapsed.recs">{{ rCollapsed.recs ? '▸' : '▾' }}</button>
        </div>
        <RecommendationList v-show="!rCollapsed.recs" :recommendations="recommendations" />
      </div>
    </aside>
  </div>

  <ChatOverlay
    v-for="w in chatWindows"
    :key="w.id"
    :vehicle-id="w.vehicleId"
    :dtc-code="w.dtcCode"
    :expanded="activeChatId === w.id"
    @minimize="activeChatId = null"
    @close="closeChat(w.id)"
  />

  <div v-if="minimizedChats.length" class="chat-dock">
    <button
      v-for="w in minimizedChats"
      :key="w.id"
      class="chat-tab"
      @click="activeChatId = w.id"
    >
      🤖 {{ w.vehicleId }} · {{ w.dtcCode }}
    </button>
  </div>

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

const chatWindows  = ref([])
const activeChatId = ref(null)
const rCollapsed   = ref({ health: false, pred: false, recs: false })

const detailVisible   = ref(false)
const detailVehicleId = ref(null)

const activeCount   = computed(() => fleet.value.filter(v => v.timestamp !== null).length)
const errorCount    = computed(() => alerts.value.filter(a => a.is_active).length)
const minimizedChats = computed(() => chatWindows.value.filter(w => w.id !== activeChatId.value))

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
  const existing = chatWindows.value.find(w => w.vehicleId === vehicleId && w.dtcCode === dtcCode)
  if (existing) {
    activeChatId.value = existing.id
    return
  }
  const id = `${vehicleId}_${dtcCode}_${Date.now()}`
  chatWindows.value.push({ id, vehicleId, dtcCode })
  activeChatId.value = id
}

function closeChat(id) {
  chatWindows.value = chatWindows.value.filter(w => w.id !== id)
  if (activeChatId.value === id)
    activeChatId.value = chatWindows.value.length ? chatWindows.value[chatWindows.value.length - 1].id : null
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

.collapse-btn {
  margin-left: auto; background: none; border: none;
  color: var(--muted); font-size: .7rem; cursor: pointer;
  padding: 0 2px; line-height: 1; transition: color .15s;
}
.collapse-btn:hover { color: var(--accent); }
.s-section.collapsed { flex: 0 0 auto !important; max-height: none !important; }

.chat-dock {
  position: fixed; bottom: 0; left: 50%; transform: translateX(-50%);
  display: flex; gap: 6px; padding: 6px 10px;
  background: var(--panel); border: 1px solid var(--border);
  border-bottom: none; border-radius: 8px 8px 0 0;
  z-index: 999;
}
.chat-tab {
  font-family: var(--mono); font-size: .65rem;
  padding: 5px 14px; border-radius: 6px; cursor: pointer;
  background: rgba(0,229,255,.06); border: 1px solid var(--accent);
  color: var(--accent); transition: .15s;
}
.chat-tab:hover { background: rgba(0,229,255,.15); }
</style>
