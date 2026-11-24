<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api, { errorMessage } from '@/lib/api'
import { auth, refreshUser } from '@/lib/auth'
import { BANKS, PLAN_DETAILS, SIM_METHODS, TX_STATUS, formatDateTime, rupiah, txItem } from '@/lib/content'
import { loadSnap } from '@/lib/snap'

const props = defineProps({ orderId: { type: String, default: '' } })
const route = useRoute()
const router = useRouter()

const PACKS = ['1', '3', '5']

function parseRequest(query) {
  if (query.paket === 'middle' || query.paket === 'high') return { kind: 'upgrade', plan: query.paket }
  if (query.jenis === 'analisis' && PACKS.includes(String(query.jumlah))) return { kind: 'pay_per_check', quantity: Number(query.jumlah) }
  return null
}

const request = props.orderId ? null : parseRequest(route.query)
if (!props.orderId && !request) router.replace({ name: 'plans' })

const overview = ref(null)
const tx = ref(null)
const loading = ref(true)
const missing = ref(false)
const error = ref('')
const busy = ref(false)
const simMethod = ref(SIM_METHODS[0].key)
const snapError = ref('')
const embedReady = ref(false)
const confirming = ref(false)
const copied = ref('')
const now = ref(Date.now())
let pollTimer = null
let clockTimer = null

const buyer = computed(() => auth.user ?? {})
const item = computed(() => txItem(tx.value ?? request))
const amount = computed(() => {
  if (tx.value) return tx.value.amount
  if (!overview.value || !request) return 0
  return request.kind === 'upgrade' ? overview.value.upgrade_prices[request.plan] : overview.value.pay_per_check_price * request.quantity
})
const validity = computed(() => {
  const kind = tx.value?.kind ?? request?.kind
  return kind === 'upgrade' ? `Berlaku ${overview.value?.period_days ?? 30} hari sejak pembayaran berhasil` : 'Tidak hangus saat bulan berganti'
})
const status = computed(() => TX_STATUS[tx.value?.status])
const groupedVa = computed(() => (tx.value?.va_number ?? '').replace(/(.{4})/g, '$1 ').trim())
const bankName = computed(() => BANKS[tx.value?.bank] ?? '')
const snapOrder = computed(() => tx.value?.status === 'pending' && !tx.value.va_number)
const snapReady = computed(() => overview.value?.provider === 'midtrans' && !!overview.value.snap_client_key && !!overview.value.snap_script_url)
const usesEmbed = computed(() => snapOrder.value && tx.value.provider === 'midtrans' && snapReady.value)
let embeddedToken = ''

const planInfo = computed(() => PLAN_DETAILS.find((p) => p.key === (tx.value?.plan ?? request?.plan)))
const benefits = computed(() => {
  const kind = tx.value?.kind ?? request?.kind
  if (kind === 'upgrade') return planInfo.value ? [...planInfo.value.limits, ...planInfo.value.features] : []
  const quantity = tx.value?.quantity ?? request?.quantity ?? 1
  return [`${quantity} analisis tambahan`, 'Tidak hangus saat bulan berganti', 'Dipakai setelah kuota bulananmu habis']
})
const stepper = computed(() => {
  const paid = tx.value?.status === 'paid'
  return [
    { label: 'Pilih paket', done: true, current: false },
    { label: 'Bayar', done: paid, current: !paid },
    { label: 'Selesai', done: paid, current: paid },
  ]
})

const expiresAt = computed(() => (tx.value ? new Date(tx.value.expires_at + (tx.value.expires_at.endsWith('Z') ? '' : 'Z')).getTime() : 0))
const remaining = computed(() => Math.max(0, Math.floor((expiresAt.value - now.value) / 1000)))
const countdown = computed(() => {
  const r = remaining.value
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(Math.floor(r / 3600))}:${pad(Math.floor((r % 3600) / 60))}:${pad(r % 60)}`
})

const steps = computed(() => [
  `Buka aplikasi mobile banking atau ATM ${bankName.value}.`,
  'Pilih menu Transfer, lalu Virtual Account.',
  `Masukkan nomor Virtual Account ${groupedVa.value} dan pastikan nominal ${rupiah(amount.value)}.`,
  'Selesaikan pembayaran. Status di halaman ini berubah otomatis dalam beberapa detik.',
])

async function load() {
  try {
    overview.value = (await api.get('/billing/overview')).data
    if (props.orderId) {
      tx.value = (await api.get(`/billing/transactions/${props.orderId}`)).data
      watchPending()
    }
  } catch (e) {
    if (e.response?.status === 404) missing.value = true
    else error.value = errorMessage(e, 'Gagal memuat halaman pembayaran. Muat ulang halaman.')
  } finally {
    loading.value = false
  }
  if (usesEmbed.value) {
    await nextTick()
    mountEmbed()
  }
  if (!props.orderId && request && overview.value && overview.value.provider !== 'unavailable' && !tx.value) await create()
}

async function mountEmbed() {
  if (!usesEmbed.value || embeddedToken === tx.value.snap_token) return
  snapError.value = ''
  embedReady.value = false
  embeddedToken = tx.value.snap_token
  try {
    const snap = await loadSnap(overview.value.snap_script_url, overview.value.snap_client_key)
    await nextTick()
    snap.embed(tx.value.snap_token, {
      embedId: 'snap-embed',
      onSuccess: () => poll(),
      onPending: () => poll(),
      onError: () => (snapError.value = 'Pembayaran tidak dapat diproses. Coba lagi atau pilih metode lain.'),
      onClose: () => {},
    })
    embedReady.value = true
  } catch {
    embeddedToken = ''
    snapError.value = 'Metode pembayaran gagal dimuat. Periksa koneksi lalu coba lagi.'
  }
}

function watchPending() {
  stopTimers()
  if (tx.value?.status !== 'pending') return
  pollTimer = setInterval(poll, 3000)
  clockTimer = setInterval(() => (now.value = Date.now()), 1000)
}

function stopTimers() {
  clearInterval(pollTimer)
  clearInterval(clockTimer)
}

async function poll() {
  try {
    const { data } = await api.get(`/billing/transactions/${tx.value.order_id}`)
    if (data.status !== tx.value.status) {
      tx.value = data
      if (data.status === 'paid') refreshUser()
    }
    if (data.status !== 'pending') stopTimers()
  } catch {
    return
  }
}

watch(remaining, (value) => {
  if (value === 0 && tx.value?.status === 'pending') poll()
})

async function create() {
  if (busy.value) return
  busy.value = true
  error.value = ''
  const body = { kind: request.kind, ...(request.kind === 'upgrade' ? { plan: request.plan } : { quantity: request.quantity }) }
  try {
    const { data } = await api.post('/billing/checkout', body)
    await router.replace({ name: 'order', params: { orderId: data.order_id } })
  } catch (e) {
    error.value = errorMessage(e, 'Gagal membuat pembayaran. Coba lagi.')
  } finally {
    busy.value = false
  }
}

async function act(path, fallback, body) {
  busy.value = true
  error.value = ''
  try {
    const { data } = body ? await api.post(path, body) : await api.post(path)
    tx.value = data
    confirming.value = false
    if (data.status !== 'pending') stopTimers()
    if (data.status === 'paid') refreshUser()
  } catch (e) {
    error.value = errorMessage(e, fallback)
  } finally {
    busy.value = false
  }
}

const cancel = () => act(`/billing/transactions/${tx.value.order_id}/cancel`, 'Gagal membatalkan pembayaran.')
const simulate = () => act(`/billing/transactions/${tx.value.order_id}/simulate-pay`, 'Gagal mensimulasikan pembayaran.')
const simulateMethod = () => act(`/billing/transactions/${tx.value.order_id}/simulate-pay`, 'Gagal mensimulasikan pembayaran.', { method: simMethod.value })

async function copy(kind, text) {
  try {
    await navigator.clipboard.writeText(text)
    copied.value = kind
    setTimeout(() => (copied.value = ''), 1800)
  } catch {
    return
  }
}

watch(
  () => props.orderId,
  (id, previous) => {
    if (!id || id === previous || tx.value?.order_id === id) return
    tx.value = null
    loading.value = true
    load()
  },
)

onMounted(() => {
  if (props.orderId || request) load()
})
onBeforeUnmount(stopTimers)
</script>

<template>
  <div class="container-page space-y-8 py-10">
    <header class="space-y-2">
      <p class="eyebrow">Pembayaran</p>
      <h1 class="text-3xl font-semibold sm:text-4xl">Selesaikan pembayaranmu</h1>
      <ol data-test="steps" class="flex flex-wrap items-center gap-2 pt-1 text-sm" aria-label="Langkah pembayaran">
        <li v-for="(s, i) in stepper" :key="s.label" class="flex items-center gap-2">
          <span
            aria-hidden="true"
            class="grid size-6 place-items-center rounded-full text-xs font-semibold"
            :class="s.done ? 'bg-navy text-white' : s.current ? 'bg-amber text-navy' : 'bg-sand text-muted'"
          >
            <Icon v-if="s.done" icon="lucide:check" class="size-3.5" />
            <template v-else>{{ i + 1 }}</template>
          </span>
          <span data-test="step-label" :aria-current="s.current ? 'step' : undefined" :class="s.current ? 'font-semibold text-navy' : 'text-muted'">{{ s.label }}</span>
          <Icon v-if="i < stepper.length - 1" icon="lucide:chevron-right" class="size-4 text-line" />
        </li>
      </ol>
    </header>

    <div v-if="loading" class="flex items-center justify-center gap-2 py-24 text-muted">
      <Icon icon="lucide:loader-circle" class="size-5 animate-spin" />
      Memuat…
    </div>

    <div v-else-if="missing" class="card grid place-items-center gap-3 px-6 py-16 text-center">
      <Icon icon="lucide:file-x" class="size-10 text-lavender" />
      <p class="font-display text-lg text-navy">Pembayaran tidak ditemukan</p>
      <RouterLink :to="{ name: 'plans' }" class="btn btn-primary btn-sm">Ke halaman paket</RouterLink>
    </div>

    <p v-else-if="!overview || (orderId && !tx)" role="alert" class="rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">{{ error }}</p>

    <div v-else class="grid items-start gap-6 lg:grid-cols-[1fr_22rem]">
      <section class="space-y-6">
        <p v-if="overview.provider === 'simulated'" class="flex items-start gap-2 rounded-lg bg-amber/15 px-3 py-2.5 text-xs text-navy">
          <Icon icon="lucide:flask-conical" class="mt-0.5 size-4 shrink-0" />
          Mode simulasi: tidak ada uang sungguhan. Metode dan nomor pembayaran hanya contoh.
        </p>
        <p v-if="overview.provider === 'unavailable'" role="alert" class="rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">
          Pembayaran belum tersedia. Coba lagi nanti.
        </p>

        <!-- Pesanan sedang disiapkan (langsung, tanpa tombol lanjut) -->
        <template v-if="!tx">
          <article v-if="overview.provider !== 'unavailable'" data-test="preparing" class="card space-y-4 p-6">
            <template v-if="error">
              <p role="alert" class="rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">{{ error }}</p>
              <button type="button" class="btn btn-primary btn-sm" :disabled="busy" @click="create">Coba lagi</button>
            </template>
            <p v-else class="flex items-center gap-2 text-sm text-muted">
              <Icon icon="lucide:loader-circle" class="size-4 animate-spin" />
              Menyiapkan pembayaran…
            </p>
          </article>
        </template>

        <!-- Langkah 2: menunggu pembayaran, metode dipilih di dalam halaman -->
        <template v-else-if="tx.status === 'pending' && !tx.va_number">
          <article class="card space-y-5 p-6">
            <div class="space-y-1">
              <p class="eyebrow">Pembayaran</p>
              <h2 class="text-xl font-semibold">Pilih metode pembayaran</h2>
            </div>
            <div class="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-paper px-4 py-3">
              <div>
                <p class="eyebrow">Total pembayaran</p>
                <p class="font-display text-2xl font-semibold text-navy tabular-nums">{{ rupiah(tx.amount) }}</p>
              </div>
              <p class="flex items-center gap-2 text-sm font-semibold text-navy">
                <Icon icon="lucide:timer" class="size-4" />
                Sisa waktu <span data-test="countdown" class="font-display tabular-nums">{{ countdown }}</span>
              </p>
            </div>

            <div v-if="tx.provider === 'simulated'" data-test="sim-panel" class="space-y-3 rounded-xl border border-dashed border-amber p-4">
              <p class="eyebrow">Simulasi Midtrans</p>
              <fieldset data-test="sim-method" class="grid gap-2 sm:grid-cols-2">
                <legend class="sr-only">Metode pembayaran contoh</legend>
                <label
                  v-for="m in SIM_METHODS"
                  :key="m.key"
                  class="flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-sm font-semibold text-navy transition has-[:checked]:border-navy has-[:checked]:bg-sand"
                  :class="simMethod === m.key ? 'border-navy' : 'border-line'"
                >
                  <input v-model="simMethod" type="radio" name="sim-method" :value="m.key" class="size-4 accent-navy" />
                  {{ m.label }}
                </label>
              </fieldset>
              <button type="button" class="btn btn-accent btn-sm" :disabled="busy" @click="simulateMethod">
                <Icon icon="lucide:flask-conical" class="size-4" />
                Simulasikan pembayaran berhasil
              </button>
            </div>

            <div v-else-if="usesEmbed">
              <div v-if="!embedReady && !snapError" data-test="embed-placeholder" class="grid min-h-64 place-items-center gap-2 text-sm text-muted">
                <Icon icon="lucide:loader-circle" class="size-6 animate-spin text-navy" />
                Memuat metode pembayaran…
              </div>
              <div id="snap-embed" class="min-h-48" />
              <div v-if="snapError" class="space-y-2 pt-2">
                <p role="alert" class="rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">{{ snapError }}</p>
                <button type="button" class="btn btn-quiet btn-sm" @click="mountEmbed">Coba lagi</button>
              </div>
            </div>

            <p v-else role="alert" class="rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">Pembayaran belum tersedia. Coba lagi nanti.</p>

            <p class="flex items-center gap-2 text-sm text-muted">
              <Icon icon="lucide:loader-circle" class="size-4 animate-spin" />
              Menunggu pembayaran. Halaman ini memperbarui status otomatis.
            </p>
          </article>

          <p v-if="error" role="alert" class="rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">{{ error }}</p>

          <div class="flex flex-wrap items-center justify-between gap-3">
            <div v-if="confirming" data-test="confirm-cancel" class="flex flex-wrap items-center gap-2 rounded-xl border border-danger/30 bg-danger/5 px-3 py-2 text-sm">
              <span class="text-navy">Batalkan pembayaran ini?</span>
              <button type="button" class="btn btn-primary btn-sm !bg-danger" :disabled="busy" @click="cancel">Ya, batalkan</button>
              <button type="button" class="btn btn-quiet btn-sm" :disabled="busy" @click="confirming = false">Kembali</button>
            </div>
            <button v-else type="button" class="btn btn-quiet btn-sm hover:!bg-danger/10 hover:!text-danger" :disabled="busy" @click="confirming = true">Batalkan pembayaran</button>
          </div>
        </template>

        <!-- Langkah 2 (pesanan lama): transfer ke Virtual Account -->
        <template v-else-if="tx.status === 'pending'">
          <article class="card space-y-5 p-6">
            <div class="space-y-1">
              <p class="eyebrow">Transfer ke Virtual Account {{ bankName }}</p>
              <div class="flex flex-wrap items-center justify-between gap-3">
                <span class="font-display text-3xl font-semibold tracking-wide text-navy tabular-nums" aria-label="Nomor Virtual Account">{{ groupedVa }}</span>
                <button type="button" data-test="copy-va" class="btn btn-quiet btn-sm shrink-0" @click="copy('va', tx.va_number)">
                  <Icon :icon="copied === 'va' ? 'lucide:check' : 'lucide:copy'" class="size-4" />
                  {{ copied === 'va' ? 'Tersalin' : 'Salin nomor' }}
                </button>
              </div>
            </div>
            <div class="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-paper px-4 py-3">
              <div>
                <p class="eyebrow">Nominal yang harus ditransfer</p>
                <p class="font-display text-2xl font-semibold text-navy tabular-nums">{{ rupiah(tx.amount) }}</p>
              </div>
              <button type="button" data-test="copy-amount" class="btn btn-quiet btn-sm shrink-0" @click="copy('amount', String(tx.amount))">
                <Icon :icon="copied === 'amount' ? 'lucide:check' : 'lucide:copy'" class="size-4" />
                {{ copied === 'amount' ? 'Tersalin' : 'Salin nominal' }}
              </button>
            </div>
            <div class="flex flex-wrap items-center justify-between gap-3 text-sm">
              <p class="text-muted">Bayar sebelum {{ formatDateTime(tx.expires_at) }}</p>
              <p class="flex items-center gap-2 font-semibold text-navy">
                <Icon icon="lucide:timer" class="size-4" />
                Sisa waktu <span data-test="countdown" class="font-display tabular-nums">{{ countdown }}</span>
              </p>
            </div>
            <p class="flex items-center gap-2 text-sm text-muted">
              <Icon icon="lucide:loader-circle" class="size-4 animate-spin" />
              Menunggu pembayaran. Halaman ini memperbarui status otomatis.
            </p>
          </article>

          <article data-test="howto" class="card space-y-3 p-6">
            <h2 class="text-lg font-semibold">Cara membayar lewat {{ bankName }}</h2>
            <ol class="list-decimal space-y-2 pl-5 text-sm text-ink">
              <li v-for="s in steps" :key="s">{{ s }}</li>
            </ol>
          </article>

          <p v-if="error" role="alert" class="rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">{{ error }}</p>

          <div class="flex flex-wrap items-center justify-between gap-3">
            <div v-if="confirming" data-test="confirm-cancel" class="flex flex-wrap items-center gap-2 rounded-xl border border-danger/30 bg-danger/5 px-3 py-2 text-sm">
              <span class="text-navy">Batalkan pembayaran ini?</span>
              <button type="button" class="btn btn-primary btn-sm !bg-danger" :disabled="busy" @click="cancel">Ya, batalkan</button>
              <button type="button" class="btn btn-quiet btn-sm" :disabled="busy" @click="confirming = false">Kembali</button>
            </div>
            <button v-else type="button" class="btn btn-quiet btn-sm hover:!bg-danger/10 hover:!text-danger" :disabled="busy" @click="confirming = true">Batalkan pembayaran</button>
            <button v-if="tx.provider === 'simulated'" type="button" class="btn btn-accent btn-sm" :disabled="busy" @click="simulate">
              <Icon icon="lucide:flask-conical" class="size-4" />
              Simulasikan pembayaran berhasil
            </button>
          </div>
        </template>

        <!-- Langkah 3: hasil -->
        <article v-else class="card grid place-items-center gap-4 px-6 py-12 text-center">
          <Icon :icon="status.icon" class="size-14" :class="tx.status === 'paid' ? 'text-navy' : 'text-muted'" />
          <div class="space-y-1">
            <h2 class="font-display text-2xl text-navy">
              {{ tx.status === 'paid' ? 'Pembayaran berhasil' : tx.status === 'expired' ? (tx.va_number ? 'Virtual Account kedaluwarsa' : 'Pembayaran kedaluwarsa') : tx.status === 'cancelled' ? 'Pembayaran dibatalkan' : 'Pembayaran gagal' }}
            </h2>
            <p class="max-w-md text-sm text-muted">
              <template v-if="tx.status === 'paid'">Invoice dikirim ke email akunmu. Fitur barumu sudah aktif.</template>
              <template v-else>Belum ada uang yang terpotong. Kamu bisa membuat pembayaran baru.</template>
            </p>
          </div>
          <div class="flex flex-wrap justify-center gap-2">
            <template v-if="tx.status === 'paid'">
              <RouterLink :to="{ name: 'invoice', params: { orderId: tx.order_id } }" class="btn btn-accent btn-sm">Lihat invoice</RouterLink>
              <RouterLink :to="{ name: 'library' }" class="btn btn-primary btn-sm">Ke koleksi</RouterLink>
              <RouterLink :to="{ name: 'profile', hash: '#riwayat' }" class="btn btn-outline btn-sm">Lihat riwayat</RouterLink>
            </template>
            <RouterLink v-else :to="{ name: 'plans' }" class="btn btn-primary btn-sm">Buat pembayaran baru</RouterLink>
          </div>
        </article>
      </section>

      <div class="space-y-5 lg:sticky lg:top-6">
      <aside data-test="summary" class="card space-y-4 p-6" aria-label="Ringkasan pesanan">
        <h2 class="text-lg font-semibold">Ringkasan pesanan</h2>
        <dl class="space-y-3 text-sm">
          <div v-if="tx" class="flex justify-between gap-3">
            <dt class="text-muted">Nomor pesanan</dt>
            <dd data-test="order-id" class="font-semibold break-all text-navy">{{ tx.order_id }}</dd>
          </div>
          <div v-if="tx" class="flex justify-between gap-3">
            <dt class="text-muted">Status</dt>
            <dd><span class="chip" :class="status.cls"><Icon :icon="status.icon" class="size-3" />{{ status.label }}</span></dd>
          </div>
          <div class="flex justify-between gap-3">
            <dt class="text-muted">Item</dt>
            <dd class="text-right font-semibold text-navy">{{ item }}</dd>
          </div>
          <div class="flex justify-between gap-3">
            <dt class="text-muted">Masa berlaku</dt>
            <dd class="text-right text-navy">{{ validity }}</dd>
          </div>
          <div data-test="buyer" class="flex justify-between gap-3">
            <dt class="text-muted">Akun</dt>
            <dd class="min-w-0 text-right text-navy"><span class="block truncate font-semibold">{{ buyer.name }}</span><span class="block truncate text-xs text-muted">{{ buyer.email }}</span></dd>
          </div>
        </dl>
        <div class="flex items-baseline justify-between border-t border-line pt-4">
          <span class="eyebrow">Total</span>
          <span class="font-display text-2xl font-semibold text-navy tabular-nums">{{ rupiah(amount) }}</span>
        </div>
      </aside>

      <section v-if="benefits.length" data-test="benefits" class="card space-y-3 p-6" aria-label="Yang kamu dapatkan">
        <h2 class="text-lg font-semibold">Yang kamu dapatkan</h2>
        <ul class="space-y-2 text-sm text-ink">
          <li v-for="b in benefits" :key="b" class="flex items-start gap-2">
            <Icon icon="lucide:check" class="mt-0.5 size-4 shrink-0 text-navy" />
            {{ b }}
          </li>
        </ul>
      </section>

      <section data-test="trust" class="card space-y-3 p-6" aria-label="Pembayaran aman">
        <h2 class="text-lg font-semibold">Pembayaran aman</h2>
        <ul class="space-y-2 text-sm text-ink">
          <li class="flex items-start gap-2">
            <Icon icon="lucide:shield-check" class="mt-0.5 size-4 shrink-0 text-navy" />
            Diproses oleh Midtrans. NARAtive tidak menyimpan data kartu atau rekening.
          </li>
          <li class="flex items-start gap-2">
            <Icon icon="lucide:zap" class="mt-0.5 size-4 shrink-0 text-navy" />
            Paket atau analisis aktif otomatis begitu pembayaran berhasil.
          </li>
          <li class="flex items-start gap-2">
            <Icon icon="lucide:file-text" class="mt-0.5 size-4 shrink-0 text-navy" />
            Invoice tersedia di Riwayat setelah pembayaran berhasil.
          </li>
        </ul>
        <p class="text-xs text-muted">
          Uang sudah terpotong tetapi belum tercatat? Buka
          <RouterLink :to="{ name: 'profile', hash: '#riwayat' }" class="font-semibold text-navy underline">Riwayat</RouterLink>
          lalu tekan Periksa status, atau hubungi admin dengan nomor pesananmu.
        </p>
      </section>
      </div>
    </div>
  </div>
</template>
