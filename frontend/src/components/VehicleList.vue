<template>
  <div class="vehicle-list">
    <div v-if="!active.length" class="no-data">Завантаження...</div>
    <div
      v-for="v in active"
      :key="v.vehicle_id"
      class="vc"
      :class="[statusClass(v), { active: selected === v.vehicle_id }]"
      @click="$emit('select', v.vehicle_id)"
    >
      <div class="vc-top">
        <span class="vc-id">{{ v.vehicle_id }}</span>
        <div style="display:flex;align-items:center;gap:6px">
          <span class="badge" :class="badgeCls(v)">{{ badgeTxt(v) }}</span>
          <button class="info-btn" @click.stop="$emit('detail', v.vehicle_id)" title="Повна телеметрія">ℹ</button>
        </div>
      </div>
      <div class="vc-metrics">
        <div>
          <div class="vc-m-val">{{ fmt(v.soc_pct, 1) }}%</div>
          <div class="vc-m-lbl">SOC</div>
        </div>
        <div>
          <div class="vc-m-val">{{ fmt(v.battery_temp_c, 1) }}°C</div>
          <div class="vc-m-lbl">Батарея</div>
        </div>
        <div>
          <div class="vc-m-val">{{ fmt(v.speed_kph, 0) }}</div>
          <div class="vc-m-lbl">км/год</div>
        </div>
      </div>
      <div class="soc-bar">
        <div class="soc-fill" :class="socFillCls(v.soc_pct)" :style="{ width: (v.soc_pct || 0) + '%' }"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  vehicles: { type: Array, default: () => [] },
  selected: { type: String, default: null },
})
defineEmits(['select', 'detail'])

const active = computed(() => props.vehicles.filter(v => v.timestamp !== null))

function fmt(val, decimals) {
  return val != null ? (+val).toFixed(decimals) : '—'
}

function statusClass(v) {
  if (v.active_error_code && !['None', '', 'null'].includes(String(v.active_error_code))) return 'error'
  if (v.soc_pct !== null && v.soc_pct < 20) return 'warn'
  if (v.battery_temp_c !== null && v.battery_temp_c > 55) return 'warn'
  return 'ok'
}

function badgeCls(v) {
  return { 'b-ok': statusClass(v) === 'ok', 'b-warn': statusClass(v) === 'warn', 'b-error': statusClass(v) === 'error' }
}

function badgeTxt(v) {
  return { ok: 'OK', warn: 'ПОПЕРЕДЖЕННЯ', error: 'ПОМИЛКА' }[statusClass(v)]
}

function socFillCls(soc) {
  if (soc == null) return ''
  return soc < 15 ? 'crit' : soc < 25 ? 'low' : ''
}
</script>

<style scoped>
.vehicle-list { flex: 1; overflow-y: auto; padding: 6px; }

.vc {
  background: rgba(255,255,255,.02);
  border: 1px solid var(--border);
  border-radius: 8px; padding: 9px 11px; margin-bottom: 5px;
  cursor: pointer; transition: .2s; position: relative; overflow: hidden;
}
.vc::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0;
  width: 3px; border-radius: 2px 0 0 2px; background: var(--green);
}
.vc.warn::before  { background: var(--amber); }
.vc.error::before { background: var(--red); }
.vc:hover, .vc.active { border-color: var(--accent); background: rgba(0,229,255,.05); }

.vc-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.vc-id  { font-family: var(--mono); font-size: .78rem; color: var(--accent); }

.badge  { font-size: .58rem; padding: 2px 7px; border-radius: 10px; font-family: var(--mono); }
.b-ok    { background: rgba(0,255,136,.1);  color: var(--green); }
.b-warn  { background: rgba(255,179,0,.1);  color: var(--amber); }
.b-error { background: rgba(255,61,61,.1);  color: var(--red); }

.vc-metrics { display: grid; grid-template-columns: repeat(3,1fr); gap: 4px; }
.vc-m-val { font-family: var(--mono); font-size: .8rem; }
.vc-m-lbl { font-size: .57rem; color: var(--muted); }

.soc-bar  { height: 3px; background: var(--border); border-radius: 2px; margin-top: 6px; overflow: hidden; }
.soc-fill { height: 100%; border-radius: 2px; transition: width .8s ease; background: var(--green); }
.soc-fill.low  { background: var(--amber); }
.soc-fill.crit { background: var(--red); }

.info-btn {
  background: rgba(0,229,255,.08); border: 1px solid var(--border);
  color: var(--muted); border-radius: 4px;
  width: 20px; height: 20px; font-size: .65rem;
  cursor: pointer; line-height: 1; padding: 0;
  transition: .2s; flex-shrink: 0;
}
.info-btn:hover { border-color: var(--accent); color: var(--accent); }
</style>
