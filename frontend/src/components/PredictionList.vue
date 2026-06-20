<template>
  <div class="scroll-list">
    <div v-if="!predictions.length" class="no-data">Прогнозів ще немає</div>
    <div v-for="p in predictions" :key="p.vehicle_id + p.predicted_at" class="pred-item">
      <div class="pred-top">
        <span class="pred-vid">{{ p.vehicle_id }}</span>
        <span class="pred-ts">{{ new Date(p.predicted_at).toLocaleTimeString('uk-UA') }}</span>
      </div>
      <div class="pred-values">
        <div class="pred-box">
          <div class="pred-num">{{ (+p.current_soc).toFixed(1) }}%</div>
          <div class="pred-lbl">Зараз SOC</div>
        </div>
        <div class="pred-box">
          <div class="pred-num" :style="{ color: predColor(p.predicted_soc) }">
            {{ (+p.predicted_soc).toFixed(1) }}%
          </div>
          <div class="pred-lbl">Прогноз</div>
        </div>
      </div>
      <div class="pred-delta" :class="delta(p) < 0 ? 'delta-neg' : 'delta-pos'">
        {{ delta(p) > 0 ? '+' : '' }}{{ delta(p).toFixed(1) }}% зміна
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({ predictions: { type: Array, default: () => [] } })

function predColor(soc) {
  return soc < 15 ? 'var(--red)' : soc < 25 ? 'var(--amber)' : 'var(--green)'
}
function delta(p) {
  return p.predicted_soc - p.current_soc
}
</script>

<style scoped>
.pred-item {
  background: rgba(0,229,255,.04); border: 1px solid var(--border);
  border-radius: 8px; padding: 10px 12px; margin-bottom: 6px;
}
.pred-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.pred-vid  { font-family: var(--mono); font-size: .78rem; color: var(--accent); }
.pred-ts   { font-size: .6rem; color: var(--muted); }

.pred-values { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.pred-box {
  background: rgba(255,255,255,.03); border: 1px solid var(--border);
  border-radius: 6px; padding: 6px 8px; text-align: center;
}
.pred-num { font-family: var(--mono); font-size: 1.1rem; color: var(--text); }
.pred-lbl { font-size: .58rem; color: var(--muted); margin-top: 2px; }

.pred-delta { font-family: var(--mono); font-size: .65rem; text-align: center; margin-top: 4px; }
.delta-neg  { color: var(--red); }
.delta-pos  { color: var(--green); }
</style>
