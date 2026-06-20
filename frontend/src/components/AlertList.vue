<template>
  <div class="scroll-list">
    <div v-if="hasInactive" class="alerts-toolbar">
      <button class="btn-clear-inactive" @click="showInactive = !showInactive">
        {{ showInactive ? '✕ Сховати неактивні' : '↺ Показати всі' }}
      </button>
    </div>

    <div v-if="!visible.length" class="no-data">✓ Помилок не виявлено</div>

    <div
      v-for="a in visible"
      :key="a.vehicle_id + a.type + (a.error_code || '')"
      class="alert-item"
      :class="[{ resolved: !a.is_active }, `alert-${a.type}`]"
    >
      <span>{{ a.is_active ? '⚠' : '✓' }}</span>
      <div style="flex:1">
        <div class="a-vid">
          {{ a.vehicle_id }} — {{ a.brand }} {{ a.model }}
          <span class="badge-type" :class="`bt-${a.type}`">{{ a.type === 'sensor' ? 'СЕНСОР' : 'DTC' }}</span>
          <span v-if="!a.is_active" class="badge-resolved">неактивна</span>
        </div>
        <div class="a-code">{{ displayCode(a) }}</div>
        <div class="a-ts">{{ new Date(a.timestamp).toLocaleTimeString('uk-UA') }}</div>
        <button
          v-if="a.is_active"
          class="btn-ask-ai"
          @click="$emit('ask-ai', a.vehicle_id, a.error_code)"
        >🤖 Запитати AI</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({ alerts: { type: Array, default: () => [] } })
defineEmits(['ask-ai'])

const showInactive = ref(true)

const hasInactive = computed(() => props.alerts.some(a => !a.is_active))

const visible = computed(() =>
  showInactive.value ? props.alerts : props.alerts.filter(a => a.is_active)
)

const sensorNames = {
  'SENSOR_CAM_BLIND':    'Засліплення фронтальної камери',
  'SENSOR_ARR_DEGRADED': 'Деградація масиву сенсорів (LiDAR/Radar)',
  'SENSOR_ARR_ERROR':    'Відмова масиву сенсорів',
  'ADAS_SAFE_STOP':      'Примусова безпечна зупинка',
}

function displayCode(a) {
  if (a.type === 'sensor') return sensorNames[a.error_code] || a.error_code
  return a.error_code
}
</script>

<style scoped>
.alerts-toolbar {
  display: flex;
  justify-content: flex-end;
  padding: 0 2px 5px;
}
.btn-clear-inactive {
  font-family: var(--mono);
  font-size: .56rem;
  padding: 2px 8px;
  border-radius: 4px;
  cursor: pointer;
  background: rgba(255,255,255,.04);
  border: 1px solid rgba(255,255,255,.1);
  color: var(--muted);
  transition: .15s;
}
.btn-clear-inactive:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.alert-item {
  display: flex; gap: 8px; align-items: flex-start;
  padding: 7px 8px; border-radius: 6px; margin-bottom: 5px;
  font-size: .7rem;
}
.alert-dtc    { background: rgba(255,61,61,.06);  border: 1px solid rgba(255,61,61,.2); }
.alert-sensor { background: rgba(255,179,0,.06);  border: 1px solid rgba(255,179,0,.25); }
.alert-item.resolved {
  background: rgba(255,255,255,.02);
  border-color: rgba(255,255,255,.08);
  opacity: .45;
}

.a-vid  { font-family: var(--mono); color: var(--red); display: flex; align-items: center; flex-wrap: wrap; gap: 5px; }
.alert-sensor .a-vid { color: var(--amber); }
.a-code { color: var(--amber); font-family: var(--mono); margin-top: 2px; font-size: .68rem; }
.alert-sensor .a-code { color: var(--accent); font-family: var(--sans); font-size: .67rem; }
.a-ts   { font-size: .6rem; color: var(--muted); }
.alert-item.resolved .a-vid  { color: var(--muted); }
.alert-item.resolved .a-code { color: var(--muted); }

.badge-type {
  font-family: var(--mono); font-size: .54rem;
  padding: 1px 5px; border-radius: 8px;
}
.bt-dtc    { background: rgba(255,61,61,.15);  color: var(--red); }
.bt-sensor { background: rgba(255,179,0,.15);  color: var(--amber); }

.badge-resolved {
  font-family: var(--mono); font-size: .58rem;
  padding: 1px 6px; border-radius: 10px;
  background: rgba(255,255,255,.06); color: var(--muted);
}
.btn-ask-ai {
  display: inline-flex; align-items: center; gap: 4px;
  margin-top: 5px; padding: 3px 8px; border-radius: 4px; cursor: pointer;
  font-family: var(--mono); font-size: .58rem;
  background: rgba(179,136,255,.12); border: 1px solid rgba(179,136,255,.35);
  color: var(--purple); transition: .2s;
}
.btn-ask-ai:hover { background: rgba(179,136,255,.28); }
</style>
