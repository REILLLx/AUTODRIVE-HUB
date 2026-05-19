<template>
  <header>
    <div class="logo">
      <div class="logo-dot"></div>
      AUTODRIVE HUB
    </div>

    <div class="sim-controls">
      <button class="sim-btn start" :disabled="simRunning" @click="startSim">
        ▶ Старт
      </button>
      <button class="sim-btn pause" :disabled="!simRunning" @click="togglePause">
        {{ simPaused ? '▶ Продовжити' : '⏸ Пауза' }}
      </button>
      <button class="sim-btn stop" :disabled="!simRunning" @click="stopSim">
        ⏹ Стоп
      </button>
      <button class="sim-btn clear" @click="clearDb">
        🗑 Очистити БД
      </button>
      <span class="sim-status" :class="simRunning ? (simPaused ? 'paused' : 'on') : 'off'">
        {{ simRunning ? (simPaused ? '⏸ Симуляція на паузі' : '● Симуляція активна') : '○ Симуляція зупинена' }}
      </span>
    </div>

    <div class="header-right">
      <span class="clock">{{ clock }}</span>
      <span class="live-badge">● LIVE</span>
    </div>
  </header>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const clock      = ref('--:--:--')
const simRunning = ref(false)
const simPaused  = ref(false)

async function fetchStatus() {
  try {
    const r = await fetch('/api/simulation/status')
    const d = await r.json()
    simRunning.value = d.running
    simPaused.value  = d.paused
  } catch {}
}

async function startSim() {
  await fetch('/api/simulation/start', { method: 'POST' })
  simRunning.value = true
}

async function stopSim() {
  await fetch('/api/simulation/stop', { method: 'POST' })
  simRunning.value = false
  simPaused.value  = false
}

async function togglePause() {
  if (simPaused.value) {
    await fetch('/api/simulation/resume', { method: 'POST' })
    simPaused.value = false
  } else {
    await fetch('/api/simulation/pause', { method: 'POST' })
    simPaused.value = true
  }
}

async function clearDb() {
  if (!confirm('Очистити всі таблиці телеметрії? Цю дію неможливо скасувати.')) return
  await fetch('/api/db/clear', { method: 'POST' })
}

let clockTimer, statusTimer
onMounted(() => {
  const tick = () => clock.value = new Date().toLocaleTimeString('uk-UA')
  tick()
  clockTimer  = setInterval(tick, 1000)
  fetchStatus()
  statusTimer = setInterval(fetchStatus, 3000)
})
onUnmounted(() => {
  clearInterval(clockTimer)
  clearInterval(statusTimer)
})
</script>

<style scoped>
header {
  background: var(--panel);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  position: relative;
}
header::after {
  content: '';
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--accent), transparent);
  opacity: .3;
}
.logo {
  font-family: var(--mono);
  font-size: 1.1rem;
  color: var(--accent);
  letter-spacing: .15em;
  display: flex;
  align-items: center;
  gap: 10px;
}
.logo-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--green);
  box-shadow: 0 0 8px var(--green);
  animation: pulse 2s infinite;
}

.sim-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sim-btn {
  font-family: var(--mono);
  font-size: .65rem;
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
  border: 1px solid;
  transition: .2s;
  letter-spacing: .05em;
}
.sim-btn:disabled { opacity: .35; cursor: not-allowed; }

.sim-btn.start {
  background: rgba(0,200,83,.1);
  border-color: var(--green);
  color: var(--green);
}
.sim-btn.start:not(:disabled):hover { background: rgba(0,200,83,.25); }

.sim-btn.pause {
  background: rgba(255,193,7,.1);
  border-color: #ffc107;
  color: #ffc107;
}
.sim-btn.pause:not(:disabled):hover { background: rgba(255,193,7,.25); }

.sim-btn.stop {
  background: rgba(255,61,61,.1);
  border-color: var(--red);
  color: var(--red);
}
.sim-btn.stop:not(:disabled):hover { background: rgba(255,61,61,.25); }

.sim-btn.clear {
  background: rgba(255,255,255,.04);
  border-color: var(--border);
  color: var(--muted);
}
.sim-btn.clear:hover { background: rgba(255,255,255,.1); color: #fff; }

.sim-status {
  font-family: var(--mono);
  font-size: .6rem;
  margin-left: 4px;
}
.sim-status.on     { color: var(--green); }
.sim-status.off    { color: var(--muted); }
.sim-status.paused { color: #ffc107; }

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
  font-family: var(--mono);
  font-size: .75rem;
  color: var(--muted);
}
.clock { color: var(--accent); }
.live-badge {
  padding: 3px 10px;
  border: 1px solid var(--green);
  border-radius: 20px;
  font-size: .7rem;
  color: var(--green);
}
</style>
