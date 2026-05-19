<template>
  <div v-if="visible" class="overlay" @click.self="$emit('close')">
    <div class="dp">

      <!-- Header -->
      <div class="dp-header">
        <div class="dp-title">
          <span class="dp-id">{{ vehicle.vehicle_id }}</span>
          <span class="dp-model">{{ vehicle.brand }} {{ vehicle.model }}</span>
          <span v-if="vehicle.plate_number" class="dp-plate">{{ vehicle.plate_number }}</span>
        </div>
        <div class="dp-header-right">
          <span class="badge" :class="badgeCls">{{ badgeTxt }}</span>
          <button class="close-btn" @click="$emit('close')">✕</button>
        </div>
      </div>

      <!-- Metrics grid -->
      <div class="dp-grid">

        <div class="dp-card accent-card">
          <div class="dc-lbl">Заряд (SOC)</div>
          <div class="dc-val" :style="{ color: socColor }">{{ fmt(vehicle.soc_pct, 1) }}%</div>
          <div class="mini-bar"><div class="mini-fill" :style="{ width: clamp(vehicle.soc_pct) + '%', background: socColor }"/></div>
        </div>

        <div class="dp-card">
          <div class="dc-lbl">Стан батареї (SOH)</div>
          <div class="dc-val" :style="{ color: sohColor }">{{ fmt(vehicle.soh_pct, 1) }}%</div>
          <div class="mini-bar"><div class="mini-fill" :style="{ width: clamp(vehicle.soh_pct) + '%', background: sohColor }"/></div>
        </div>

        <div class="dp-card">
          <div class="dc-lbl">Температура батареї</div>
          <div class="dc-val" :style="{ color: tempColor }">{{ fmt(vehicle.battery_temp_c, 1) }}°C</div>
          <div class="dc-hint">Норма: до 50°C</div>
        </div>

        <div class="dp-card">
          <div class="dc-lbl">Швидкість</div>
          <div class="dc-val">{{ fmt(vehicle.speed_kph, 0) }}<span class="dc-unit"> км/год</span></div>
        </div>

        <div class="dp-card">
          <div class="dc-lbl">Знос гальмівних колодок</div>
          <div class="dc-val" :style="{ color: brakeColor }">{{ fmt(vehicle.brake_pad_wear_mm, 2) }}<span class="dc-unit"> мм</span></div>
          <div class="mini-bar">
            <div class="mini-fill" :style="{ width: brakePercent + '%', background: brakeColor }"/>
          </div>
          <div class="dc-hint">Критичний поріг: 2.5 мм</div>
        </div>

        <div class="dp-card">
          <div class="dc-lbl">Датчик ABS</div>
          <div class="dc-val" :style="{ color: vehicle.abs_fault_indicator ? 'var(--red)' : 'var(--green)' }">
            {{ vehicle.abs_fault_indicator ? 'Спрацював' : 'Норма' }}
          </div>
        </div>

        <div class="dp-card">
          <div class="dc-lbl">Активна помилка (DTC)</div>
          <div class="dc-val" :style="{ color: hasError ? 'var(--red)' : 'var(--green)' }">
            {{ hasError ? vehicle.active_error_code : 'Відсутня' }}
          </div>
        </div>

        <div class="dp-card">
          <div class="dc-lbl">GPS координати</div>
          <div class="dc-val dc-gps">{{ fmtGps(vehicle.lat) }}, {{ fmtGps(vehicle.lon) }}</div>
        </div>

        <div class="dp-card">
          <div class="dc-lbl">Температура повітря</div>
          <div class="dc-val">{{ fmt(vehicle.ambient_temp_c, 1) }}<span class="dc-unit"> °C</span></div>
          <div class="dc-hint">Навколишнє середовище</div>
        </div>

        <div class="dp-card">
          <div class="dc-lbl">Струм батареї</div>
          <div class="dc-val" :style="{ color: currentColor }">
            {{ vehicle.battery_current_a != null ? (vehicle.battery_current_a > 0 ? '+' : '') + fmt(vehicle.battery_current_a, 1) : '—' }}<span class="dc-unit"> А</span>
          </div>
          <div class="dc-hint">{{ (vehicle.battery_current_a ?? 0) < 0 ? 'Заряджання' : 'Розряджання' }}</div>
        </div>

        <div class="dp-card">
          <div class="dc-lbl">Споживання потужності</div>
          <div class="dc-val">{{ fmt(vehicle.power_kw, 1) }}<span class="dc-unit"> кВт</span></div>
        </div>

      </div>

      <!-- LSTM prediction -->
      <div v-if="prediction" class="dp-lstm">
        <span class="lstm-lbl">Прогноз заряду через 1 годину:</span>
        <span class="lstm-cur">{{ fmt(prediction.current_soc, 1) }}%</span>
        <span class="lstm-arrow">→</span>
        <span class="lstm-pred" :style="{ color: predColor }">{{ fmt(prediction.predicted_soc, 1) }}%</span>
        <span class="lstm-delta" :class="deltaVal >= 0 ? 'pos' : 'neg'">
          {{ deltaVal >= 0 ? '+' : '' }}{{ deltaVal.toFixed(1) }}%
        </span>
      </div>

      <div class="dp-footer">
        Оновлено: {{ vehicle.timestamp ? new Date(vehicle.timestamp).toLocaleTimeString('uk-UA') : '—' }}
      </div>

    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  visible:    { type: Boolean, default: false },
  vehicle:    { type: Object,  default: () => ({}) },
  prediction: { type: Object,  default: null },
})
defineEmits(['close'])

function fmt(val, dec) { return val != null ? (+val).toFixed(dec) : '—' }
function clamp(v) { return Math.min(100, Math.max(0, v || 0)) }
function fmtGps(v) { return v != null ? (+v).toFixed(5) : '—' }

const hasError = computed(() =>
  props.vehicle.active_error_code &&
  !['None', '', 'null'].includes(String(props.vehicle.active_error_code))
)

const statusCls = computed(() => {
  if (hasError.value) return 'error'
  if ((props.vehicle.soc_pct ?? 100) < 20) return 'warn'
  if ((props.vehicle.battery_temp_c ?? 0) > 55) return 'warn'
  return 'ok'
})
const badgeCls = computed(() => ({ 'b-ok': statusCls.value === 'ok', 'b-warn': statusCls.value === 'warn', 'b-error': statusCls.value === 'error' }))
const badgeTxt = computed(() => ({ ok: 'OK', warn: 'ПОПЕРЕДЖЕННЯ', error: 'ПОМИЛКА' }[statusCls.value]))

const socColor  = computed(() => {
  const s = props.vehicle.soc_pct ?? 100
  return s < 15 ? 'var(--red)' : s < 25 ? 'var(--amber)' : 'var(--green)'
})
const sohColor  = computed(() => {
  const s = props.vehicle.soh_pct ?? 100
  return s < 80 ? 'var(--red)' : s < 85 ? 'var(--amber)' : 'var(--green)'
})
const tempColor = computed(() => {
  const t = props.vehicle.battery_temp_c ?? 0
  return t > 65 ? 'var(--red)' : t > 50 ? 'var(--amber)' : 'var(--accent)'
})
const brakeColor = computed(() => {
  const b = props.vehicle.brake_pad_wear_mm ?? 8
  return b < 2.5 ? 'var(--red)' : b < 4 ? 'var(--amber)' : 'var(--green)'
})
const brakePercent = computed(() => {
  const b = Math.min(8, Math.max(0, props.vehicle.brake_pad_wear_mm ?? 8))
  return (b / 8) * 100
})

const currentColor = computed(() => {
  const a = props.vehicle.battery_current_a ?? 0
  return a < 0 ? 'var(--green)' : a > 80 ? 'var(--red)' : 'var(--accent)'
})

const deltaVal  = computed(() => {
  if (!props.prediction) return 0
  return (props.prediction.predicted_soc ?? 0) - (props.prediction.current_soc ?? 0)
})
const predColor = computed(() => {
  const p = props.prediction?.predicted_soc ?? 100
  return p < 15 ? 'var(--red)' : p < 20 ? 'var(--amber)' : 'var(--green)'
})
</script>

<style scoped>
.overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,.6);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(2px);
}
.dp {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 12px;
  width: 560px;
  max-height: 90vh;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.dp-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  border-bottom: 1px solid var(--border); padding-bottom: 12px;
}
.dp-title { display: flex; flex-direction: column; gap: 3px; }
.dp-id    { font-family: var(--mono); font-size: 1.1rem; color: var(--accent); }
.dp-model { font-size: .7rem; color: var(--muted); }
.dp-plate {
  font-family: var(--mono); font-size: .68rem;
  color: var(--accent); background: rgba(0,229,255,.08);
  border: 1px solid rgba(0,229,255,.2);
  border-radius: 4px; padding: 1px 7px;
  letter-spacing: .1em; align-self: flex-start;
}
.dp-header-right { display: flex; align-items: center; gap: 10px; }

.badge { font-size: .6rem; padding: 3px 9px; border-radius: 10px; font-family: var(--mono); }
.b-ok    { background: rgba(0,255,136,.1);  color: var(--green); }
.b-warn  { background: rgba(255,179,0,.1);  color: var(--amber); }
.b-error { background: rgba(255,61,61,.1);  color: var(--red); }

.close-btn {
  background: none; border: 1px solid var(--border);
  color: var(--muted); border-radius: 6px;
  width: 26px; height: 26px; cursor: pointer;
  font-size: .8rem; line-height: 1;
  transition: .2s;
}
.close-btn:hover { border-color: var(--accent); color: var(--accent); }

.dp-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.dp-card {
  background: rgba(255,255,255,.03);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
}
.accent-card { border-color: rgba(0,229,255,.2); }

.dc-lbl  { font-size: .58rem; color: var(--muted); margin-bottom: 4px; letter-spacing: .05em; }
.dc-val  { font-family: var(--mono); font-size: 1.1rem; }
.dc-unit { font-size: .65rem; color: var(--muted); }
.dc-gps  { font-size: .72rem; }
.dc-hint { font-size: .55rem; color: var(--muted); margin-top: 3px; }

.mini-bar {
  height: 4px; background: rgba(255,255,255,.07);
  border-radius: 2px; overflow: hidden; margin-top: 6px;
}
.mini-fill { height: 100%; border-radius: 2px; transition: width .5s ease; }

.dp-lstm {
  display: flex; align-items: center; gap: 8px;
  background: rgba(0,229,255,.04);
  border: 1px solid rgba(0,229,255,.15);
  border-radius: 8px; padding: 10px 14px;
  font-family: var(--mono);
}
.lstm-lbl   { font-size: .6rem; color: var(--muted); flex: 1; }
.lstm-cur   { font-size: .85rem; color: var(--muted); }
.lstm-arrow { color: var(--muted); }
.lstm-pred  { font-size: .95rem; font-weight: 700; }
.lstm-delta { font-size: .75rem; }
.lstm-delta.pos { color: var(--green); }
.lstm-delta.neg { color: var(--red); }

.dp-footer {
  font-size: .6rem; color: var(--muted);
  text-align: right; padding-top: 4px;
  border-top: 1px solid var(--border);
  font-family: var(--mono);
}
</style>
