<template>
  <div class="chat-overlay" :class="{ open: visible }" @click.self="$emit('close')">
    <div class="chat-panel">

      <div class="chat-header">
        <div>
          <div class="chat-title">🤖 AI Асистент{{ dtcCode ? ` — ${dtcCode}` : '' }}</div>
          <div class="chat-subtitle">{{ subtitle }}</div>
        </div>
        <button class="chat-close" @click="$emit('close')">✕</button>
      </div>

      <div ref="msgBox" class="chat-messages">
        <div
          v-for="(msg, i) in messages"
          :key="i"
          class="chat-msg"
          :class="[msg.role, { typing: msg.typing }]"
        >
          <div class="msg-sender">{{ msg.role === 'ai' ? '🤖 AI Асистент' : '👤 Оператор' }}</div>
          <div v-html="formatText(msg.content)"></div>
        </div>
      </div>

      <div class="chat-input-row">
        <input
          ref="inputEl"
          v-model="inputText"
          class="chat-input"
          placeholder="Введіть питання оператора..."
          :disabled="busy"
          @keydown.enter.prevent="send"
        />
        <button class="chat-send" :disabled="busy" @click="send">Надіслати ↵</button>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  visible:   { type: Boolean, default: false },
  vehicleId: { type: String,  default: '' },
  dtcCode:   { type: String,  default: '' },
})
defineEmits(['close'])

const messages  = ref([])
const inputText = ref('')
const subtitle  = ref('Очікування...')
const busy      = ref(false)
const sessionId = ref(null)
const msgBox    = ref(null)
const inputEl   = ref(null)

watch(() => props.visible, async (val) => {
  if (!val) return
  messages.value  = []
  inputText.value = ''
  sessionId.value = null
  busy.value      = false
  subtitle.value  = `${props.vehicleId} · ініціалізація...`

  pushMsg('ai', '⏳ Аналізую телеметрію та базу знань...', true)

  try {
    const res = await fetch('/api/chat/init', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ vehicle_id: props.vehicleId, dtc_code: props.dtcCode }),
    }).then(r => r.json())

    if (res.error) throw new Error(res.error)
    sessionId.value = res.session_id
    removeTyping()
    pushMsg('ai', res.initial_message)
    subtitle.value = `${props.vehicleId} · ${props.dtcCode}`
    await nextTick()
    inputEl.value?.focus()
  } catch (e) {
    removeTyping()
    pushMsg('ai', `⚠️ Помилка ініціалізації: ${e.message}`)
  }
})

async function send() {
  if (busy.value || !sessionId.value) return
  const text = inputText.value.trim()
  if (!text) return

  busy.value      = true
  inputText.value = ''
  pushMsg('user', text)
  pushMsg('ai', '🤖 Аналізую...', true)

  try {
    const res = await fetch('/api/chat/message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId.value, message: text }),
    }).then(r => r.json())

    removeTyping()
    if (res.error) throw new Error(res.error)
    pushMsg('ai', res.response)
  } catch (e) {
    removeTyping()
    pushMsg('ai', `⚠️ Помилка: ${e.message}`)
  } finally {
    busy.value = false
    await nextTick()
    inputEl.value?.focus()
  }
}

function pushMsg(role, content, typing = false) {
  messages.value.push({ role, content, typing })
  nextTick(() => { if (msgBox.value) msgBox.value.scrollTop = msgBox.value.scrollHeight })
}

function removeTyping() {
  const idx = messages.value.findLastIndex(m => m.typing)
  if (idx !== -1) messages.value.splice(idx, 1)
}

function formatText(text) {
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>')
    .replace(/•/g, '&bull;')
}
</script>

<style scoped>
.chat-overlay {
  display: none; position: fixed; inset: 0;
  background: rgba(0,0,0,.55); z-index: 1000;
  align-items: center; justify-content: center;
}
.chat-overlay.open { display: flex; }

.chat-panel {
  width: 480px; max-width: 96vw; height: 620px; max-height: 90vh;
  background: var(--panel); border: 1px solid var(--border);
  border-radius: 12px; display: flex; flex-direction: column;
  box-shadow: 0 0 60px rgba(0,229,255,.08), 0 24px 48px rgba(0,0,0,.6);
  animation: chatSlideIn .22s ease;
}

.chat-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; border-bottom: 1px solid var(--border); flex-shrink: 0;
}
.chat-title    { font-family: var(--mono); font-size: .8rem; color: var(--accent); }
.chat-subtitle { font-size: .62rem; color: var(--muted); margin-top: 2px; }
.chat-close {
  cursor: pointer; color: var(--muted); font-size: 1rem;
  padding: 4px 8px; border-radius: 4px; background: none; border: none; transition: .15s;
}
.chat-close:hover { color: var(--red); background: rgba(255,61,61,.1); }

.chat-messages {
  flex: 1; overflow-y: auto; padding: 14px 14px 8px;
  display: flex; flex-direction: column; gap: 10px;
}

.chat-msg {
  max-width: 88%; padding: 9px 12px; border-radius: 10px;
  font-size: .72rem; line-height: 1.55; animation: msgIn .18s ease;
}
.chat-msg.ai {
  align-self: flex-start;
  background: rgba(179,136,255,.08); border: 1px solid rgba(179,136,255,.2);
  color: var(--text); border-radius: 2px 10px 10px 10px;
}
.chat-msg.user {
  align-self: flex-end;
  background: rgba(0,229,255,.08); border: 1px solid rgba(0,229,255,.2);
  color: var(--text); border-radius: 10px 2px 10px 10px;
}
.chat-msg.typing {
  align-self: flex-start;
  background: rgba(179,136,255,.05); border: 1px solid rgba(179,136,255,.15);
  color: var(--muted); font-style: italic; font-size: .68rem;
}
.msg-sender {
  font-family: var(--mono); font-size: .58rem;
  color: var(--purple); margin-bottom: 4px;
}
.chat-msg.user .msg-sender { color: var(--accent); text-align: right; }

.chat-input-row {
  display: flex; gap: 8px; padding: 12px 14px;
  border-top: 1px solid var(--border); flex-shrink: 0;
}
.chat-input {
  flex: 1; background: rgba(255,255,255,.04); border: 1px solid var(--border);
  border-radius: 6px; padding: 8px 12px; color: var(--text);
  font-family: var(--sans); font-size: .75rem; outline: none;
  transition: border-color .2s; height: 38px;
}
.chat-input:focus { border-color: var(--accent); }
.chat-input::placeholder { color: var(--muted); }
.chat-send {
  padding: 0 16px; border-radius: 6px; cursor: pointer;
  font-family: var(--mono); font-size: .7rem;
  background: rgba(0,229,255,.1); border: 1px solid var(--accent);
  color: var(--accent); transition: .2s;
}
.chat-send:hover:not(:disabled) { background: rgba(0,229,255,.22); }
.chat-send:disabled { opacity: .4; cursor: default; }
</style>
