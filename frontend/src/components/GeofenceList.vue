<template>
  <div class="scroll-list">
    <div v-if="!events.length" class="no-data">Подій ще немає</div>
    <div v-for="e in events.slice(0, 10)" :key="e.timestamp + e.vehicle_code" class="geo-item">
      <div class="geo-top">
        <span class="geo-vid">{{ e.vehicle_code }}</span>
        <span :class="e.event_type === 'ENTERED' ? 'geo-entered' : 'geo-exited'">
          {{ e.event_type === 'ENTERED' ? '🟢 В депо' : '🔴 Виїхав' }}
        </span>
      </div>
      <div class="geo-meta">{{ e.brand }} {{ e.model }} · {{ new Date(e.timestamp).toLocaleTimeString('uk-UA') }}</div>
    </div>
  </div>
</template>

<script setup>
defineProps({ events: { type: Array, default: () => [] } })
</script>

<style scoped>
.geo-item {
  padding: 7px 8px; border-radius: 6px; margin-bottom: 4px;
  border: 1px solid var(--border); font-size: .7rem;
  background: rgba(0,229,255,.02);
}
.geo-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 3px; }
.geo-vid     { font-family: var(--mono); font-size: .75rem; color: var(--accent); }
.geo-entered { color: var(--green); font-family: var(--mono); font-size: .65rem; }
.geo-exited  { color: var(--amber); font-family: var(--mono); font-size: .65rem; }
.geo-meta    { color: var(--muted); font-size: .62rem; }
</style>
