<template>
  <div class="fh-panel">
    <div class="fh-top">
      <div class="fh-gauge-wrap">
        <svg viewBox="0 0 120 68" class="fh-gauge">
          <path d="M 10,64 A 50,50 0 0,1 110,64"
                fill="none" stroke="rgba(255,255,255,0.07)" stroke-width="10" stroke-linecap="round"/>
          <path d="M 10,64 A 50,50 0 0,1 110,64"
                fill="none" :stroke="fleetColor" stroke-width="10" stroke-linecap="round"
                pathLength="100"
                :stroke-dasharray="health.fleet_score + ' 100'"
                style="transition:stroke-dasharray .5s ease"/>
        </svg>
        <div class="fh-score-box">
          <span class="fh-score" :style="{ color: fleetColor }">{{ health.fleet_score }}</span>
          <span class="fh-pct">%</span>
        </div>
      </div>

      <div class="fh-legend">
        <div class="fh-leg-item"><span class="dot ok"></span>Норма ≥ 70%</div>
        <div class="fh-leg-item"><span class="dot warn"></span>Увага 40–69%</div>
        <div class="fh-leg-item"><span class="dot critical"></span>Критично &lt; 40%</div>
      </div>
    </div>

    <div class="fh-vehicles">
      <div v-for="v in health.vehicles" :key="v.vehicle_id" class="fh-vrow">
        <span class="fh-vid">{{ v.vehicle_id }}</span>
        <div class="fh-track">
          <div class="fh-fill" :style="{ width: v.health + '%', background: getColor(v.status) }"/>
        </div>
        <span class="fh-val" :style="{ color: getColor(v.status) }">{{ v.health }}%</span>
      </div>
    </div>

    <div class="fh-weights">
      <span>SOC 30%</span><span>SOH 25%</span><span>Темп 20%</span>
      <span>Гальма 15%</span><span>Помилки 10%</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  health: { type: Object, default: () => ({ fleet_score: 0, vehicles: [] }) }
})

function getColor(status) {
  if (status === 'ok')       return 'var(--green)'
  if (status === 'warn')     return 'var(--amber)'
  return 'var(--red)'
}

const fleetStatus = computed(() => {
  const s = props.health.fleet_score
  if (s >= 70) return 'ok'
  if (s >= 40) return 'warn'
  return 'critical'
})

const fleetColor = computed(() => getColor(fleetStatus.value))
</script>

<style scoped>
.fh-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 2px 0;
}

.fh-top {
  display: flex;
  align-items: center;
  gap: 10px;
}

.fh-gauge-wrap {
  position: relative;
  width: 110px;
  flex-shrink: 0;
}

.fh-gauge { width: 100%; display: block; }

.fh-score-box {
  position: absolute;
  bottom: 2px;
  left: 50%;
  transform: translateX(-50%);
  text-align: center;
  line-height: 1;
}

.fh-score {
  font-family: var(--mono);
  font-size: 1.35rem;
  font-weight: 700;
}

.fh-pct {
  font-size: .65rem;
  color: var(--muted);
  margin-left: 1px;
}

.fh-legend {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.fh-leg-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: .6rem;
  color: var(--muted);
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot.ok       { background: var(--green); }
.dot.warn     { background: var(--amber); }
.dot.critical { background: var(--red);   }

.fh-vehicles {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.fh-vrow {
  display: grid;
  grid-template-columns: 80px 1fr 42px;
  align-items: center;
  gap: 6px;
}

.fh-vid {
  font-size: .62rem;
  color: var(--muted);
  white-space: nowrap;
}

.fh-track {
  height: 6px;
  background: rgba(255,255,255,0.07);
  border-radius: 3px;
  overflow: hidden;
}

.fh-fill {
  height: 100%;
  border-radius: 3px;
  transition: width .5s ease;
}

.fh-val {
  font-family: var(--mono);
  font-size: .65rem;
  text-align: right;
}

.fh-weights {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 8px;
  font-size: .55rem;
  color: rgba(255,255,255,0.2);
  padding-top: 2px;
  border-top: 1px solid var(--border);
}
</style>
