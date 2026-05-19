<template>
  <div class="scroll-list">
    <div v-if="!alerts.length" class="no-data">✓ Помилок не виявлено</div>
    <div
      v-for="a in alerts"
      :key="a.vehicle_id + a.timestamp"
      class="alert-item"
      :class="{ resolved: !a.is_active }"
    >
      <span>{{ a.is_active ? '⚠' : '✓' }}</span>
      <div style="flex:1">
        <div class="a-vid">
          {{ a.vehicle_id }} — {{ a.brand }} {{ a.model }}
          <span v-if="!a.is_active" class="badge-resolved">неактивна</span>
        </div>
        <div class="a-code">{{ a.active_error_code }}</div>
        <div class="a-ts">{{ new Date(a.timestamp).toLocaleTimeString('uk-UA') }}</div>
        <button
          v-if="a.is_active"
          class="btn-ask-ai"
          @click="$emit('ask-ai', a.vehicle_id, a.active_error_code)"
        >🤖 Запитати AI</button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({ alerts: { type: Array, default: () => [] } })
defineEmits(['ask-ai'])
</script>

<style scoped>
.alert-item {
  display: flex; gap: 8px; align-items: flex-start;
  padding: 7px 8px; border-radius: 6px; margin-bottom: 5px;
  background: rgba(255,61,61,.06); border: 1px solid rgba(255,61,61,.2); font-size: .7rem;
}
.alert-item.resolved {
  background: rgba(255,255,255,.02);
  border-color: rgba(255,255,255,.08);
  opacity: .55;
}
.a-vid  { font-family: var(--mono); color: var(--red); }
.a-code { color: var(--amber); font-family: var(--mono); }
.a-ts   { font-size: .6rem; color: var(--muted); }
.alert-item.resolved .a-vid  { color: var(--muted); }
.alert-item.resolved .a-code { color: var(--muted); }
.badge-resolved {
  font-family: var(--mono); font-size: .58rem;
  padding: 1px 6px; border-radius: 10px;
  background: rgba(255,255,255,.06); color: var(--muted); margin-left: 6px;
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
