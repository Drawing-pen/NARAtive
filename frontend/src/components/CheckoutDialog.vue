<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import api, { errorMessage } from '@/lib/api'
import { BANKS, TX_STATUS, formatDateTime, rupiah, txItem } from '@/lib/content'

const props = defineProps({
  request: { type: Object, default: null },        // pesanan baru: { kind, plan?, quantity?, amount }
  resume: { type: Object, default: null },         // transaksi yang masih menunggu, untuk dilanjutkan
  banks: { type: Array, required: true },
  provider: { type: String, default: 'simulated' },
})
const emit = defineEmits(['close', 'changed'])

const tx = ref(props.resume)
const bank = ref(props.resume?.bank ?? props.banks[0])
const busy = ref(false)
const error = ref('')
const copied = ref(false)
let timer = null

const item = computed(() => (tx.value ? txItem(tx.value) : txItem({ kind: props.request.kind, plan: props.request.plan, quantity: props.request.quantity })))
const amount = computed(() => tx.value?.amount ?? props.request.amount)
const step = computed(() => (!tx.value ? 'bank' : tx.value.status === 'pending' ? 'pay' : 'result'))
const status = computed(() => TX_STATUS[tx.value?.status])

async function run(call, fallback) {
  busy.value = true
  error.value = ''
  try {
    return (await call()).data
  } catch (e) {
    error.value = errorMessage(e, fallback)
    return null
  } finally {
    busy.value = false
  }
}

async function create() {
  const { kind, plan, quantity } = props.request
  const body = { kind, bank: bank.value, ...(kind === 'upgrade' ? { plan } : { quantity }) }
  const data = await run(() => api.post('/billing/checkout', body), 'Gagal membuat Virtual Account. Coba lagi.')
  if (data) {
    tx.value = data
    emit('changed')
    startPolling()
  }
}

async function poll() {
  try {
    const { data } = await api.get(`/billing/transactions/${tx.value.order_id}`)
    if (data.status !== tx.value.status) {
      tx.value = data
      emit('changed')
    }
    if (data.status !== 'pending') stopPolling()
  } catch {
    /* gagal sesaat: coba lagi pada putaran berikutnya */
  }
}
const startPolling = () => {
  stopPolling()
  timer = setInterval(poll, 3000)
}
const stopPolling = () => clearInterval(timer)

async function cancel() {
  const data = await run(() => api.post(`/billing/transactions/${tx.value.order_id}/cancel`), 'Gagal membatalkan pembayaran.')
  if (data) {
    tx.value = data
    stopPolling()
    emit('changed')
  }
}

async function simulate() {
  const data = await run(() => api.post(`/billing/transactions/${tx.value.order_id}/simulate-pay`), 'Gagal mensimulasikan pembayaran.')
  if (data) {
    tx.value = data
    stopPolling()
    emit('changed')
  }
}

function retry() {
  tx.value = null
  error.value = ''
}

async function copyVa() {
  try {
    await navigator.clipboard.writeText(tx.value.va_number)
    copied.value = true
    setTimeout(() => (copied.value = false), 1800)
  } catch {
    /* clipboard tidak tersedia: nomor tetap bisa disalin manual */
  }
}

const groupedVa = computed(() => (tx.value?.va_number ?? '').replace(/(.{4})/g, '$1 ').trim())

onMounted(() => {
  if (tx.value?.status === 'pending') startPolling()
})
onBeforeUnmount(stopPolling)
</script>

<template>
  <div class="fixed inset-0 z-50 grid place-items-center bg-navy-deep/50 px-4 py-6" @click.self="!busy && emit('close')" @keydown.esc="!busy && emit('close')">
    <div role="dialog" aria-modal="true" aria-labelledby="bayar-judul" class="card flex max-h-full w-full max-w-md flex-col gap-5 overflow-y-auto p-6 shadow-xl">
      <div class="flex items-start justify-between gap-3">
        <div class="flex items-start gap-3">
          <span class="grid size-10 shrink-0 place-items-center rounded-xl bg-sand text-navy"><Icon icon="lucide:credit-card" class="size-5" /></span>
          <div class="space-y-0.5">
            <h2 id="bayar-judul" class="text-xl font-semibold">Pembayaran</h2>
            <p class="text-sm text-muted">{{ item }}</p>
          </div>
        </div>
        <button type="button" class="btn btn-quiet btn-sm !px-2" aria-label="Tutup" :disabled="busy" @click="emit('close')">
          <Icon icon="lucide:x" class="size-5" />
        </button>
      </div>

      <div class="flex items-baseline justify-between rounded-xl bg-paper px-4 py-3">
        <span class="eyebrow">Total</span>
        <span class="font-display text-2xl font-semibold text-navy tabular-nums">{{ rupiah(amount) }}</span>
      </div>

      <p v-if="provider === 'simulated'" class="flex items-start gap-2 rounded-lg bg-amber/15 px-3 py-2.5 text-xs text-navy">
        <Icon icon="lucide:flask-conical" class="mt-0.5 size-4 shrink-0" />
        Mode simulasi: tidak ada uang sungguhan. Nomor Virtual Account di bawah hanya contoh.
      </p>

      <p v-if="provider === 'unavailable'" role="alert" class="rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">
        Pembayaran belum tersedia. Coba lagi nanti.
      </p>

      <!-- 1. Pilih bank -->
      <template v-if="step === 'bank'">
        <fieldset class="space-y-2">
          <legend class="eyebrow pb-1">Pilih bank Virtual Account</legend>
          <label
            v-for="b in banks"
            :key="b"
            class="flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-sm font-semibold text-navy transition has-[:checked]:border-navy has-[:checked]:bg-sand"
            :class="bank === b ? 'border-navy' : 'border-line'"
          >
            <input v-model="bank" type="radio" name="bank" :value="b" class="size-4 accent-navy" />
            {{ BANKS[b] }}
          </label>
        </fieldset>
        <p v-if="error" role="alert" class="rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">{{ error }}</p>
        <button type="button" class="btn btn-primary" :disabled="busy || provider === 'unavailable'" @click="create">
          <Icon :icon="busy ? 'lucide:loader-circle' : 'lucide:landmark'" class="size-4.5" :class="{ 'animate-spin': busy }" />
          Buat Virtual Account
        </button>
      </template>

      <!-- 2. Menunggu pembayaran -->
      <template v-else-if="step === 'pay'">
        <div class="space-y-3 rounded-xl border border-line p-4">
          <p class="eyebrow">Transfer ke Virtual Account {{ BANKS[tx.bank] }}</p>
          <div class="flex items-center justify-between gap-3">
            <span class="font-display text-2xl font-semibold tracking-wide text-navy tabular-nums" aria-label="Nomor Virtual Account">{{ groupedVa }}</span>
            <button type="button" class="btn btn-quiet btn-sm shrink-0" @click="copyVa">
              <Icon :icon="copied ? 'lucide:check' : 'lucide:copy'" class="size-4" />
              {{ copied ? 'Tersalin' : 'Salin' }}
            </button>
          </div>
          <p class="text-xs text-muted">Bayar sebelum {{ formatDateTime(tx.expires_at) }}. Halaman ini memperbarui status otomatis.</p>
        </div>
        <p class="flex items-center gap-2 text-sm text-muted">
          <Icon icon="lucide:loader-circle" class="size-4 animate-spin" />
          Menunggu pembayaran…
        </p>
        <p v-if="error" role="alert" class="rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">{{ error }}</p>
        <div class="flex flex-wrap justify-between gap-2">
          <button type="button" class="btn btn-quiet btn-sm hover:!bg-danger/10 hover:!text-danger" :disabled="busy" @click="cancel">Batalkan pembayaran</button>
          <button v-if="tx.provider === 'simulated'" type="button" class="btn btn-accent btn-sm" :disabled="busy" @click="simulate">
            <Icon icon="lucide:flask-conical" class="size-4" />
            Simulasikan pembayaran berhasil
          </button>
        </div>
      </template>

      <!-- 3. Hasil -->
      <template v-else>
        <div class="grid place-items-center gap-3 py-2 text-center">
          <Icon :icon="status.icon" class="size-12" :class="tx.status === 'paid' ? 'text-navy' : 'text-muted'" />
          <div class="space-y-1">
            <p class="font-display text-lg text-navy">
              {{ tx.status === 'paid' ? 'Pembayaran berhasil' : tx.status === 'expired' ? 'Virtual Account kedaluwarsa' : tx.status === 'cancelled' ? 'Pembayaran dibatalkan' : 'Pembayaran gagal' }}
            </p>
            <p class="text-sm text-muted">
              <template v-if="tx.status === 'paid'">Invoice dikirim ke email akunmu. Fitur barumu sudah aktif.</template>
              <template v-else>Belum ada uang yang terpotong. Kamu bisa membuat pembayaran baru.</template>
            </p>
          </div>
        </div>
        <div class="flex justify-end gap-2">
          <button v-if="tx.status !== 'paid' && request" type="button" class="btn btn-quiet btn-sm" @click="retry">Coba lagi</button>
          <button type="button" class="btn btn-primary btn-sm" @click="emit('close')">Tutup</button>
        </div>
      </template>
    </div>
  </div>
</template>
