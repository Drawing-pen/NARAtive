<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import api, { errorMessage } from '@/lib/api'
import { isLoggedIn, refreshUser } from '@/lib/auth'
import { TX_STATUS, formatDate, rupiah, txItem } from '@/lib/content'
import CheckoutDialog from '@/components/CheckoutDialog.vue'
import TierChip from '@/components/TierChip.vue'

const route = useRoute()
const plans = [
  {
    key: 'standard', tier: 'free', name: 'Standard', tag: 'Gratis', icon: 'lucide:user',
    limits: ['50 halaman per unggahan', '3 analisis per bulan', '3 e-book aktif'],
    features: ['Rating dan rentang usia', 'Persentase konten dewasa dan bobot cerita', 'Mode baca dan Safe Mode standar'],
  },
  {
    key: 'middle', tier: 'middle', name: 'Middle', tag: 'Menengah', icon: 'lucide:sparkles',
    limits: ['300 halaman per unggahan', '15 analisis per bulan', '50 e-book aktif'],
    features: ['Semua fitur Standard', 'Rincian per dimensi dan alasan rating', 'Rangkuman cerita per bab', 'Biodata tokoh', 'Relasi antar tokoh'],
  },
  {
    key: 'high', tier: 'high', name: 'High', tag: 'Lengkap', popular: true, icon: 'lucide:crown',
    limits: ['Tanpa batas halaman', 'Tanpa batas analisis', 'Tanpa batas koleksi'],
    features: ['Semua fitur Middle', 'Profil sensitivitas personal', 'Unduh hasil analisis (PDF beranotasi)'],
  },
]
const RANK = { free: 0, middle: 1, high: 2 }
const PACKS = [1, 3, 5]

const overview = ref(null)
const transactions = ref([])
const loading = ref(isLoggedIn())
const error = ref('')
const checkout = ref(null)    // { request } atau { resume }
const quantity = ref(PACKS[0])

const paid = computed(() => overview.value?.paid_tier ?? 'free')
const devUnlocked = computed(() => overview.value && overview.value.tier !== overview.value.paid_tier)
const usage = computed(() => overview.value?.usage)
const quotaPct = computed(() => (usage.value?.monthly_limit ? Math.min(100, (usage.value.used / usage.value.monthly_limit) * 100) : 0))
const pendingCount = computed(() => transactions.value.filter((t) => t.status === 'pending').length)

async function load() {
  if (!isLoggedIn()) return
  try {
    const [o, t] = await Promise.all([api.get('/billing/overview'), api.get('/billing/transactions')])
    overview.value = o.data
    transactions.value = t.data
    error.value = ''
  } catch (e) {
    error.value = errorMessage(e, 'Gagal memuat data langganan. Muat ulang halaman.')
  } finally {
    loading.value = false
  }
}

function buyPlan(plan) {
  checkout.value = { request: { kind: 'upgrade', plan, amount: overview.value.upgrade_prices[plan] } }
}
function buyChecks() {
  checkout.value = { request: { kind: 'pay_per_check', quantity: quantity.value, amount: overview.value.pay_per_check_price * quantity.value } }
}
async function onChanged() {
  await Promise.all([load(), refreshUser()])
}

function action(p) {
  if (p.key === 'standard') return paid.value === 'free' ? { label: 'Paket aktif', disabled: true } : { label: 'Paket dasar', disabled: true }
  if (RANK[p.tier] < RANK[paid.value]) return { label: 'Di bawah paketmu', disabled: true }
  return { label: RANK[p.tier] === RANK[paid.value] ? `Perpanjang ${p.name}` : `Pilih paket ${p.name}`, disabled: false }
}

onMounted(async () => {
  await load()
  if (route.hash === '#riwayat') document.getElementById('riwayat')?.scrollIntoView({ behavior: 'smooth' })
})
</script>

<template>
  <div class="container-page space-y-12 py-12">
    <header class="max-w-2xl space-y-3">
      <p class="eyebrow">Berlangganan</p>
      <h1 class="text-4xl font-semibold sm:text-5xl">Pilih paket sesuai cara bacamu</h1>
      <p class="text-lg text-muted">Mulai gratis, naikkan tingkatan saat butuh rincian yang lebih dalam atau kuota yang lebih besar.</p>
    </header>

    <p v-if="error" role="alert" class="rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">{{ error }}</p>

    <p v-if="devUnlocked" class="flex items-start gap-2 rounded-xl bg-amber/15 px-4 py-3 text-sm text-navy">
      <Icon icon="lucide:flask-conical" class="mt-0.5 size-4 shrink-0" />
      Mode pengembangan: semua fitur dibuka tanpa berlangganan, dan batas paket tidak berlaku. Paket yang dibayar tetap {{ paid === 'free' ? 'Standard' : paid }}.
    </p>

    <!-- Pemakaian -->
    <section v-if="usage" class="card grid gap-6 p-6 sm:grid-cols-2 lg:grid-cols-4" aria-label="Pemakaian bulan ini">
      <div class="space-y-2">
        <p class="eyebrow">Analisis bulan ini</p>
        <p class="font-display text-3xl font-semibold text-navy tabular-nums">
          {{ usage.used }}<span class="text-lg text-muted"> / {{ usage.monthly_limit ?? '∞' }}</span>
        </p>
        <div v-if="usage.monthly_limit" class="h-2 overflow-hidden rounded-full bg-sand">
          <div class="h-full rounded-full bg-navy transition-all" :style="{ width: quotaPct + '%' }" />
        </div>
        <p class="text-xs text-muted">Direset {{ formatDate(usage.resets_at) }}</p>
      </div>
      <div class="space-y-2">
        <p class="eyebrow">Analisis tambahan</p>
        <p class="font-display text-3xl font-semibold text-navy tabular-nums">{{ usage.extra_checks }}</p>
        <p class="text-xs text-muted">Dipakai setelah kuota bulanan habis, tidak hangus tiap bulan.</p>
      </div>
      <div class="space-y-2">
        <p class="eyebrow">E-book aktif</p>
        <p class="font-display text-3xl font-semibold text-navy tabular-nums">
          {{ usage.active_books }}<span class="text-lg text-muted"> / {{ usage.max_active ?? '∞' }}</span>
        </p>
        <p class="text-xs text-muted">{{ usage.max_pages ? `Maksimal ${usage.max_pages} halaman per unggahan` : 'Tanpa batas halaman' }}</p>
      </div>
      <div class="space-y-2">
        <p class="eyebrow">Paketmu</p>
        <p class="flex items-center gap-2"><TierChip :tier="paid === 'free' ? 'standard' : paid" /></p>
        <p class="text-xs text-muted">{{ overview.tier_expires_at ? `Aktif sampai ${formatDate(overview.tier_expires_at)}` : paid === 'free' ? 'Gratis, tanpa masa berlaku' : 'Tanpa batas waktu' }}</p>
      </div>
    </section>

    <section class="grid gap-6 lg:grid-cols-3" aria-label="Pilihan paket">
      <article
        v-for="p in plans"
        :key="p.key"
        class="card relative flex flex-col gap-6 p-7"
        :class="p.popular ? 'border-amber ring-2 ring-amber/40' : ''"
      >
        <span v-if="p.popular" class="chip absolute -top-3 left-7 bg-amber text-navy">Paling lengkap</span>
        <div class="flex items-start justify-between gap-3">
          <div class="space-y-1">
            <span class="grid size-12 place-items-center rounded-xl bg-navy text-amber"><Icon :icon="p.icon" class="size-6" /></span>
            <h2 class="pt-3 text-2xl font-semibold">{{ p.name }}</h2>
            <p class="text-sm text-muted">{{ p.tag }}</p>
          </div>
          <TierChip v-if="p.key !== 'standard'" :tier="p.key" />
          <span v-else class="chip bg-sand text-navy"><Icon icon="lucide:user" class="size-3" />Dasar</span>
        </div>

        <div>
          <p class="font-display text-3xl font-semibold text-navy">
            <template v-if="p.key === 'standard'">Gratis</template>
            <template v-else-if="overview">{{ rupiah(overview.upgrade_prices[p.key]) }}<span class="text-base font-normal text-muted"> / {{ overview.period_days }} hari</span></template>
            <template v-else>–</template>
          </p>
        </div>

        <div class="space-y-2.5">
          <p class="eyebrow">Batas</p>
          <ul class="space-y-2 text-sm text-ink">
            <li v-for="l in p.limits" :key="l" class="flex items-start gap-2"><Icon icon="lucide:gauge" class="mt-0.5 size-4 shrink-0 text-lavender" />{{ l }}</li>
          </ul>
        </div>
        <div class="space-y-2.5">
          <p class="eyebrow">Fitur</p>
          <ul class="space-y-2 text-sm text-ink">
            <li v-for="f in p.features" :key="f" class="flex items-start gap-2"><Icon icon="lucide:check" class="mt-0.5 size-4 shrink-0 text-lavender" />{{ f }}</li>
          </ul>
        </div>

        <div class="mt-auto">
          <RouterLink v-if="!isLoggedIn() && p.key !== 'standard'" :to="{ name: 'login', query: { next: '/berlangganan' } }" class="btn w-full" :class="p.popular ? 'btn-accent' : 'btn-primary'">
            Masuk untuk memilih paket
          </RouterLink>
          <button
            v-else-if="overview"
            type="button"
            class="btn w-full"
            :class="p.key === 'standard' ? 'btn-quiet' : p.popular ? 'btn-accent' : 'btn-primary'"
            :disabled="action(p).disabled"
            @click="buyPlan(p.key)"
          >
            <Icon v-if="!action(p).disabled" icon="lucide:gem" class="size-4" />
            {{ action(p).label }}
          </button>
        </div>
      </article>
    </section>

    <section class="grid gap-6 lg:grid-cols-2">
      <article id="pay-per-check" class="card space-y-4 p-7">
        <div class="flex items-center gap-3">
          <span class="grid size-11 place-items-center rounded-xl bg-sand text-navy"><Icon icon="lucide:zap" class="size-6" /></span>
          <h2 class="text-xl font-semibold">Analisis tambahan (pay-per-check)</h2>
        </div>
        <p class="text-sm text-muted">Kuota bulanan habis? Beli analisis tambahan tanpa perlu menaikkan tingkatan akun, khusus untuk pengguna Standard dan Middle. Analisis tambahan tidak hangus saat bulan berganti.</p>
        <template v-if="overview">
          <div class="flex flex-wrap gap-2" role="radiogroup" aria-label="Jumlah analisis tambahan">
            <button
              v-for="n in PACKS"
              :key="n"
              type="button"
              role="radio"
              :aria-checked="quantity === n"
              class="btn btn-sm"
              :class="quantity === n ? 'btn-primary' : 'btn-outline'"
              @click="quantity = n"
            >
              {{ n }} analisis
            </button>
          </div>
          <div class="flex flex-wrap items-center justify-between gap-3">
            <p class="font-display text-2xl font-semibold text-navy">{{ rupiah(overview.pay_per_check_price * quantity) }}</p>
            <button type="button" class="btn btn-primary btn-sm" :disabled="paid === 'high'" @click="buyChecks">
              <Icon icon="lucide:shopping-cart" class="size-4" />
              Beli analisis tambahan
            </button>
          </div>
          <p v-if="paid === 'high'" class="text-xs text-muted">Paket High tanpa batas analisis.</p>
        </template>
        <RouterLink v-else-if="!isLoggedIn()" :to="{ name: 'login', query: { next: '/berlangganan' } }" class="btn btn-primary btn-sm">Masuk untuk membeli</RouterLink>
      </article>

      <article id="riwayat" class="card space-y-4 p-7">
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-3">
            <span class="grid size-11 place-items-center rounded-xl bg-sand text-navy"><Icon icon="lucide:receipt" class="size-6" /></span>
            <h2 class="text-xl font-semibold">Riwayat pembayaran</h2>
          </div>
          <span v-if="pendingCount" class="chip bg-amber/35 text-navy">{{ pendingCount }} menunggu</span>
        </div>

        <div v-if="loading" class="flex items-center justify-center gap-2 py-6 text-muted">
          <Icon icon="lucide:loader-circle" class="size-5 animate-spin" />
          Memuat…
        </div>
        <div v-else-if="!isLoggedIn()" class="grid place-items-center gap-2 rounded-xl border border-dashed border-line px-4 py-6 text-center">
          <Icon icon="lucide:log-in" class="size-7 text-lavender" />
          <p class="text-sm text-muted">Masuk untuk melihat riwayat pembayaranmu.</p>
        </div>
        <div v-else-if="!transactions.length" class="grid place-items-center gap-2 rounded-xl border border-dashed border-line px-4 py-6 text-center">
          <Icon icon="lucide:inbox" class="size-7 text-lavender" />
          <p class="text-sm text-muted">Belum ada riwayat pembayaran. Riwayat upgrade dan pembelian analisis akan tampil di sini.</p>
        </div>
        <ul v-else class="divide-y divide-line">
          <li v-for="t in transactions" :key="t.order_id" class="flex flex-wrap items-center gap-x-4 gap-y-2 py-3">
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-semibold text-navy">{{ txItem(t) }}</p>
              <p class="text-xs text-muted">{{ formatDate(t.created_at) }} · {{ t.order_id }}</p>
            </div>
            <span class="text-sm font-semibold text-navy tabular-nums">{{ rupiah(t.amount) }}</span>
            <span class="chip" :class="TX_STATUS[t.status].cls"><Icon :icon="TX_STATUS[t.status].icon" class="size-3" />{{ TX_STATUS[t.status].label }}</span>
            <button v-if="t.status === 'pending'" type="button" class="btn btn-accent btn-sm" @click="checkout = { resume: t }">Lanjutkan bayar</button>
          </li>
        </ul>
      </article>
    </section>

    <CheckoutDialog
      v-if="checkout"
      :request="checkout.request ?? null"
      :resume="checkout.resume ?? null"
      :banks="overview.banks"
      :provider="overview.provider"
      @close="checkout = null"
      @changed="onChanged"
    />
  </div>
</template>
