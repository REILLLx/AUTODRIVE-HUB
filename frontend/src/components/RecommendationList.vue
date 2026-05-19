<template>
  <div class="scroll-list">
    <div v-if="!recommendations.length" class="no-data">✓ Рекомендацій немає</div>
    <div
      v-for="r in recommendations"
      :key="r.vehicle_id + r.timestamp"
      class="crec-item"
      :class="`crec-${r.level}`"
    >
      <div class="crec-top">
        <span :class="`crec-vid-${r.level}`">{{ icons[r.level] }} {{ r.vehicle_id }}</span>
        <span class="crec-ts">{{ new Date(r.timestamp).toLocaleTimeString('uk-UA') }}</span>
      </div>
      <div class="crec-msg">{{ r.message }}</div>
      <div v-if="r.detail" class="crec-detail">{{ r.detail }}</div>
    </div>
  </div>
</template>

<script setup>
defineProps({ recommendations: { type: Array, default: () => [] } })

const icons = { critical: '🚨', warning: '⚠️', info: 'ℹ️' }
</script>

<style scoped>
.crec-item {
  border-radius: 8px; padding: 9px 11px;
  margin-bottom: 6px; animation: fadeIn .3s ease; font-size: .7rem;
}
.crec-critical { background: rgba(255,61,61,.06);   border: 1px solid rgba(255,61,61,.3); }
.crec-warning  { background: rgba(255,179,0,.06);   border: 1px solid rgba(255,179,0,.3); }
.crec-info     { background: rgba(0,229,255,.04);   border: 1px solid rgba(0,229,255,.2); }

.crec-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.crec-vid-critical { font-family: var(--mono); font-size: .75rem; color: var(--red); }
.crec-vid-warning  { font-family: var(--mono); font-size: .75rem; color: var(--amber); }
.crec-vid-info     { font-family: var(--mono); font-size: .75rem; color: var(--accent); }
.crec-ts     { font-size: .6rem; color: var(--muted); }
.crec-msg    { color: var(--text); line-height: 1.4; margin-bottom: 3px; }
.crec-detail { color: var(--muted); font-size: .63rem; line-height: 1.3; }
</style>
