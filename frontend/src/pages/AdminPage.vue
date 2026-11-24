<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '@/lib/api'
import { rupiah, formatDateTime } from '@/lib/content'

const data = ref(null)
const loading = ref(true)
const forbidden = ref(false)
const failed = ref(false)
const yearChoice = ref('')
const monthChoice = ref('')

const MONTHS = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
const LAST30 = { mode: 'last30', label: '30 hari terakhir', granularity: 'day', tables_label: 'Seluruh waktu', available_years: [] }
const period = computed(() => data.value?.period ?? LAST30)

async function load() {
  loading.value = true
  forbidden.value = false
  failed.value = false
  try {
    const params = {}
    if (yearChoice.value) params.year = Number(yearChoice.value)
    if (yearChoice.value && monthChoice.value) params.month = Number(monthChoice.value)
    data.value = (await (Object.keys(params).length ? api.get('/admin/overview', { params }) : api.get('/admin/overview'))).data
  } catch (e) {
    if (e?.response?.status === 403) forbidden.value = true
    else failed.value = true
  } finally {
    loading.value = false
  }
}

const orderInput = ref('')
const check = ref(null)
const checkBusy = ref(false)
const checkError = ref('')
const TX_LABEL = { paid: 'Dibayar', pending: 'Menunggu', failed: 'Gagal', expired: 'Kedaluwarsa', cancelled: 'Dibatalkan' }
const statusText = (key) => (key ? (TX_LABEL[key] ?? key) : '-')

async function runCheck(sync) {
  const id = encodeURIComponent(orderInput.value)
  checkBusy.value = true
  checkError.value = ''
  try {
    check.value = (await (sync ? api.post(`/admin/payments/${id}/sync`) : api.get(`/admin/payments/${id}`))).data
  } catch (e) {
    if (!sync) check.value = null
    checkError.value = e?.response?.status === 404 ? 'Pesanan tidak ditemukan.' : e?.response?.status === 403 ? 'Halaman ini khusus admin.' : 'Gagal memeriksa pesanan.'
  } finally {
    checkBusy.value = false
  }
}

function changeYear() {
  monthChoice.value = ''
  load()
}

onMounted(load)

const TIERS = [
  ['free', 'Standard'],
  ['middle', 'Middle'],
  ['high', 'High'],
]
const TX = [
  ['paid', 'Dibayar'],
  ['pending', 'Menunggu'],
  ['failed', 'Gagal'],
  ['expired', 'Kedaluwarsa'],
  ['cancelled', 'Dibatalkan'],
]
const PLANS = [
  ['middle', 'Paket Middle'],
  ['high', 'Paket High'],
  ['pay_per_check', 'Analisis tambahan'],
]
const DOCS = [
  ['done', 'Selesai'],
  ['analyzing', 'Dianalisis'],
  ['queued', 'Antre'],
  ['uploaded', 'Terunggah'],
  ['failed', 'Gagal'],
  ['not_novel', 'Bukan novel'],
]
const JOBS = [
  ['done', 'Selesai'],
  ['partial', 'Sebagian'],
  ['failed', 'Gagal'],
]

const cards = computed(() => {
  const d = data.value
  const p = period.value
  const running = p.mode === 'last30'
  const quotaLabel = running ? 'Mentok kuota bulan ini' : p.mode === 'month' ? `Mentok kuota ${p.label}` : 'Mentok kuota'
  return [
    {
      label: 'Total akun pengguna',
      value: d.users.total,
      note: running ? `${d.users.inactive} tidak aktif` : `${d.users.inactive} tidak aktif, ${d.users.registered ?? 0} pendaftar ${p.label}`,
    },
    {
      label: running ? 'Pendapatan bulan ini' : `Pendapatan ${p.label}`,
      value: rupiah(running ? d.revenue.paid_this_month : d.revenue.paid_in_period ?? 0),
      note: `Total ${rupiah(d.revenue.paid_total)}`,
    },
    { label: 'Total e-book', value: d.documents.total, note: `${d.documents.by_status.failed} gagal dianalisis` },
    { label: quotaLabel, value: d.quota.at_limit ?? '-', note: p.mode === 'year' ? 'Pilih satu bulan' : 'Standard dan Middle' },
  ]
})

function chart(series, key, label, format) {
  const total = series.reduce((sum, d) => sum + d[key], 0)
  const max = Math.max(1, ...series.map((d) => d[key]))
  return {
    label,
    total: format(total),
    aria: `${label} ${period.value.label}: total ${format(total)}`,
    bars: series.map((d) => ({ date: d.date, value: d[key], text: format(d[key]), pct: Math.round((d[key] / max) * 100) })),
  }
}

const charts = computed(() => [
  chart(data.value.users.signups, 'count', 'Pendaftar', (n) => String(n)),
  chart(data.value.revenue.per_day, 'amount', 'Pendapatan', rupiah),
  chart(data.value.documents.uploads, 'count', 'Unggahan', (n) => String(n)),
])

const dayLabel = (iso) =>
  new Date(iso + 'T00:00:00').toLocaleDateString('id-ID', period.value.granularity === 'month' ? { month: 'short', year: 'numeric' } : { day: 'numeric', month: 'short' })
</script>

<template>
  <div class="container-page space-y-8 py-10">
    <section class="flex flex-wrap items-end justify-between gap-3">
      <div class="space-y-2">
        <p class="eyebrow">Admin</p>
        <h1 class="text-3xl leading-tight font-semibold sm:text-4xl">Pantauan sistem</h1>
        <p class="max-w-2xl text-sm text-muted">Hanya angka ringkasan. Halaman ini tidak menampilkan data pribadi pengguna, isi e-book, atau hasil analisis per orang.</p>
      </div>
      <button v-if="data" class="btn btn-outline btn-sm" :disabled="loading" @click="load()">
        <Icon icon="lucide:refresh-cw" class="size-4" :class="{ 'animate-spin': loading }" />
        Muat ulang
      </button>
    </section>

    <div v-if="loading && !data" class="flex items-center justify-center gap-2 py-24 text-muted">
      <Icon icon="lucide:loader-circle" class="size-5 animate-spin" />
      Memuat…
    </div>

    <section v-else-if="forbidden" class="card grid place-items-center gap-3 px-6 py-16 text-center">
      <Icon icon="lucide:shield-alert" class="size-10 text-lavender" />
      <p class="font-display text-lg text-navy">Halaman ini khusus admin.</p>
    </section>

    <p v-else-if="failed && !data" role="alert" class="flex items-start gap-2 rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">
      <Icon icon="lucide:circle-alert" class="mt-0.5 size-4 shrink-0" />
      Gagal mengambil data admin.
    </p>

    <template v-else-if="data">
      <section class="card flex flex-wrap items-end gap-4 p-5" aria-label="Periode">
        <div class="space-y-1.5">
          <label for="periode-tahun" class="text-sm font-semibold text-navy">Tahun</label>
          <select id="periode-tahun" v-model="yearChoice" class="input !pl-3" :disabled="loading" @change="changeYear">
            <option value="">30 hari terakhir</option>
            <option v-for="y in period.available_years" :key="y" :value="String(y)">{{ y }}</option>
          </select>
        </div>
        <div class="space-y-1.5">
          <label for="periode-bulan" class="text-sm font-semibold text-navy">Bulan</label>
          <select id="periode-bulan" v-model="monthChoice" class="input !pl-3" :disabled="loading || !yearChoice" @change="load()">
            <option value="">Semua bulan</option>
            <option v-for="(name, i) in MONTHS" :key="name" :value="String(i + 1)">{{ name }}</option>
          </select>
        </div>
        <p class="pb-2 text-sm text-muted">Menampilkan: <span class="font-semibold text-navy">{{ period.label }}</span></p>
      </section>

      <p v-if="failed" role="alert" class="flex items-start gap-2 rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">
        <Icon icon="lucide:circle-alert" class="mt-0.5 size-4 shrink-0" />
        Gagal memuat periode yang dipilih.
      </p>

      <section class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Ringkasan">
        <article v-for="c in cards" :key="c.label" class="card space-y-1 p-5">
          <p class="text-xs font-semibold tracking-wide text-muted uppercase">{{ c.label }}</p>
          <p class="font-display text-3xl font-semibold text-navy">{{ c.value }}</p>
          <p class="text-xs text-muted">{{ c.note }}</p>
        </article>
      </section>

      <section class="card space-y-3 p-5" aria-label="Sebaran paket">
        <h2 class="text-lg font-semibold">Sebaran paket (akun aktif)</h2>
        <ul class="grid gap-3 sm:grid-cols-3">
          <li v-for="[key, label] in TIERS" :key="key" class="rounded-lg bg-paper px-4 py-3">
            <p class="text-sm text-muted">{{ label }}</p>
            <p class="font-display text-2xl font-semibold text-navy">{{ data.users.per_tier[key] }}</p>
          </li>
        </ul>
      </section>

      <section class="grid gap-5 lg:grid-cols-3" :aria-label="`Grafik ${period.label}`">
        <article v-for="c in charts" :key="c.label" class="card space-y-3 p-5">
          <div class="flex items-baseline justify-between gap-2">
            <h2 class="text-lg font-semibold">{{ c.label }}</h2>
            <span class="text-sm font-semibold text-navy">{{ c.total }}</span>
          </div>
          <div role="img" :aria-label="c.aria" class="flex h-32 items-end gap-0.5">
            <div v-for="b in c.bars" :key="b.date" data-test="bar" class="flex-1 rounded-t bg-navy/80" :style="{ height: Math.max(b.value ? 4 : 1, b.pct) + '%', opacity: b.value ? 1 : 0.2 }" :title="`${dayLabel(b.date)}: ${b.text}`"></div>
          </div>
          <div class="flex justify-between text-[11px] text-muted" aria-hidden="true">
            <span>{{ dayLabel(c.bars[0].date) }}</span>
            <span>{{ dayLabel(c.bars[c.bars.length - 1].date) }}</span>
          </div>
        </article>
      </section>

      <section class="grid gap-5 lg:grid-cols-2">
        <article class="card space-y-3 p-5">
          <h2 class="text-lg font-semibold">Transaksi</h2>
          <p class="text-xs text-muted">Periode: {{ period.tables_label }}</p>
          <table class="w-full text-sm">
            <tbody class="divide-y divide-line">
              <tr v-for="[key, label] in TX" :key="key">
                <th scope="row" class="py-2 text-left font-normal text-muted">{{ label }}</th>
                <td class="py-2 text-right font-semibold text-navy">{{ data.revenue.by_status[key] }}</td>
              </tr>
            </tbody>
          </table>
          <h3 class="pt-2 text-sm font-semibold text-navy">Pendapatan menurut jenis</h3>
          <table class="w-full text-sm">
            <tbody class="divide-y divide-line">
              <tr v-for="[key, label] in PLANS" :key="key">
                <th scope="row" class="py-2 text-left font-normal text-muted">{{ label }}</th>
                <td class="py-2 text-right text-muted">{{ data.revenue.by_plan[key].count }}x</td>
                <td class="py-2 text-right font-semibold text-navy">{{ rupiah(data.revenue.by_plan[key].amount) }}</td>
              </tr>
            </tbody>
          </table>
        </article>

        <article class="card space-y-3 p-5">
          <h2 class="text-lg font-semibold">E-book</h2>
          <p class="text-xs text-muted">Periode: {{ period.tables_label }}</p>
          <table class="w-full text-sm">
            <tbody class="divide-y divide-line">
              <tr v-for="[key, label] in DOCS" :key="key">
                <th scope="row" class="py-2 text-left font-normal text-muted">{{ label }}</th>
                <td class="py-2 text-right font-semibold text-navy">{{ data.documents.by_status[key] }}</td>
              </tr>
            </tbody>
          </table>
          <div class="grid gap-3 pt-2 sm:grid-cols-2">
            <div v-for="[group, title] in [['summary', 'Rangkuman'], ['characters', 'Tokoh dan relasi']]" :key="group" class="rounded-lg bg-paper px-4 py-3 text-sm">
              <p class="font-semibold text-navy">{{ title }}</p>
              <p v-for="[key, label] in JOBS" :key="key" class="flex justify-between text-muted">
                <span>{{ label }}</span>
                <span>{{ data.documents[group][key] }}</span>
              </p>
            </div>
          </div>
        </article>
      </section>

      <section class="card space-y-4 p-5" aria-label="Periksa pembayaran">
        <div class="space-y-1">
          <h2 class="text-lg font-semibold">Periksa pembayaran</h2>
          <p class="text-sm text-muted">Masukkan nomor pesanan dari invoice atau riwayat pengguna. Hasilnya hanya status dan nominal, tanpa data pribadi.</p>
        </div>
        <form class="flex flex-wrap items-center gap-2" @submit.prevent="runCheck(false)">
          <label for="cek-pesanan" class="sr-only">Nomor pesanan</label>
          <input id="cek-pesanan" v-model.trim="orderInput" type="text" autocomplete="off" placeholder="NAR-..." class="input min-w-0 flex-1 !pl-3" />
          <button type="submit" class="btn btn-primary btn-sm" :disabled="!orderInput || checkBusy">
            <Icon :icon="checkBusy ? 'lucide:loader-circle' : 'lucide:search'" class="size-4" :class="{ 'animate-spin': checkBusy }" />
            Periksa
          </button>
        </form>
        <p v-if="checkError" role="alert" data-test="check-error" class="rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">{{ checkError }}</p>
        <div v-if="check" data-test="check-result" class="space-y-3">
          <div class="grid gap-3 sm:grid-cols-2">
            <div data-test="check-local" class="rounded-lg bg-paper px-4 py-3 text-sm">
              <p class="font-semibold text-navy">Di NARAtive</p>
              <p class="flex justify-between text-muted"><span>Status</span><span class="text-navy">{{ statusText(check.local_status) }}</span></p>
              <p class="flex justify-between text-muted"><span>Nominal</span><span class="text-navy">{{ rupiah(check.local_amount) }}</span></p>
              <p class="flex justify-between text-muted"><span>Metode</span><span class="text-navy">{{ check.local_method ?? '-' }}</span></p>
              <p class="flex justify-between text-muted"><span>Dibuat</span><span class="text-navy">{{ formatDateTime(check.created_at) }}</span></p>
              <p v-if="check.paid_at" class="flex justify-between text-muted"><span>Dibayar</span><span class="text-navy">{{ formatDateTime(check.paid_at) }}</span></p>
            </div>
            <div data-test="check-gateway" class="rounded-lg bg-paper px-4 py-3 text-sm">
              <p class="font-semibold text-navy">Di Midtrans</p>
              <p v-if="!check.gateway.checked" class="text-muted">Tidak diperiksa</p>
              <template v-else>
                <p class="flex justify-between text-muted"><span>Status</span><span class="text-navy">{{ statusText(check.gateway.status) }} ({{ check.gateway.raw_status ?? '-' }})</span></p>
                <p class="flex justify-between text-muted"><span>Nominal</span><span class="text-navy">{{ check.gateway.amount === null ? '-' : rupiah(check.gateway.amount) }}</span></p>
                <p class="flex justify-between text-muted"><span>Metode</span><span class="text-navy">{{ check.gateway.method ?? '-' }}</span></p>
              </template>
            </div>
          </div>
          <p data-test="check-message" role="status" class="text-sm text-navy">{{ check.message }}</p>
          <button v-if="check.can_sync" type="button" data-test="sync" class="btn btn-accent btn-sm" :disabled="checkBusy" @click="runCheck(true)">
            <Icon icon="lucide:refresh-cw" class="size-4" />
            Sinkronkan
          </button>
        </div>
      </section>

      <section class="card space-y-3 p-5" aria-label="Alasan gagal">
        <h2 class="text-lg font-semibold">Alasan e-book gagal dianalisis</h2>
        <p v-if="!data.documents.failure_reasons.length" class="text-sm text-muted">Belum ada e-book yang gagal.</p>
        <ul v-else class="divide-y divide-line text-sm">
          <li v-for="r in data.documents.failure_reasons" :key="r.reason" class="flex items-center justify-between gap-3 py-2">
            <span class="min-w-0 text-navy">{{ r.reason }}</span>
            <span class="font-semibold text-navy">{{ r.count }}</span>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>
