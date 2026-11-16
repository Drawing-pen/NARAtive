<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/lib/api'
import { hasTier } from '@/lib/auth'
import { rupiah } from '@/lib/content'
import { closeUpgrade, upgrade } from '@/lib/upgrade'

const router = useRouter()
const prices = ref(null)

const plans = [
  { key: 'middle', name: 'Middle', icon: 'lucide:sparkles', perks: ['300 halaman per unggahan, 15 analisis per bulan', 'Rangkuman, tokoh, dan relasi', 'Rincian dan alasan rating'] },
  { key: 'high', name: 'High', icon: 'lucide:crown', perks: ['Tanpa batas halaman dan analisis', 'Unduh hasil analisis dalam PDF', 'Profil sensitivitas, ganti cover dan foto tokoh'] },
]

const needed = computed(() => upgrade.tier ?? (hasTier('middle') ? 'high' : 'middle'))

watch(
  () => upgrade.open,
  async (open) => {
    if (!open) return
    try {
      prices.value = (await api.get('/billing/overview')).data.upgrade_prices
    } catch {
      prices.value = null
    }
  },
  { immediate: true },
)

function choose(key) {
  closeUpgrade()
  router.push({ name: 'checkout', query: { paket: key } })
}

function go(name, extra = {}) {
  closeUpgrade()
  router.push({ name, ...extra })
}
</script>

<template>
  <div v-if="upgrade.open" data-test="backdrop" class="fixed inset-0 z-50 grid place-items-center bg-navy-deep/50 px-4 py-6" @click.self="closeUpgrade">
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="upgrade-judul"
      class="card flex max-h-full w-full max-w-2xl flex-col gap-5 overflow-y-auto p-6 shadow-xl"
      @keydown.esc="closeUpgrade"
    >
      <div class="flex items-start justify-between gap-3">
        <div class="flex items-start gap-3">
          <span class="grid size-10 shrink-0 place-items-center rounded-xl bg-navy text-amber"><Icon icon="lucide:gem" class="size-5" /></span>
          <div class="space-y-1">
            <h2 id="upgrade-judul" class="text-xl font-semibold">Tingkatkan paketmu</h2>
            <p v-if="upgrade.message" class="text-sm text-muted">{{ upgrade.message }}</p>
          </div>
        </div>
        <button type="button" class="btn btn-quiet btn-sm !px-2" aria-label="Tutup" @click="closeUpgrade">
          <Icon icon="lucide:x" class="size-5" />
        </button>
      </div>

      <div class="grid gap-4 sm:grid-cols-2">
        <article
          v-for="p in plans"
          :key="p.key"
          :data-test="`plan-${p.key}`"
          class="card flex flex-col gap-4 p-5"
          :class="needed === p.key ? 'border-amber ring-2 ring-amber/40' : ''"
        >
          <div class="flex items-start justify-between gap-2">
            <div class="flex items-center gap-2">
              <span class="grid size-9 place-items-center rounded-lg bg-sand text-navy"><Icon :icon="p.icon" class="size-5" /></span>
              <h3 class="text-lg font-semibold">{{ p.name }}</h3>
            </div>
            <span v-if="needed === p.key" class="chip bg-amber text-navy">Dibutuhkan</span>
          </div>
          <p v-if="prices" class="font-display text-2xl font-semibold text-navy">
            {{ rupiah(prices[p.key]) }}<span class="text-sm font-normal text-muted"> / 30 hari</span>
          </p>
          <ul class="space-y-2 text-sm text-ink">
            <li v-for="perk in p.perks" :key="perk" class="flex items-start gap-2">
              <Icon icon="lucide:check" class="mt-0.5 size-4 shrink-0 text-lavender" />{{ perk }}
            </li>
          </ul>
          <button
            type="button"
            class="btn mt-auto w-full"
            :class="needed === p.key ? 'btn-accent' : 'btn-primary'"
            :disabled="hasTier(p.key)"
            @click="choose(p.key)"
          >
            <template v-if="hasTier(p.key)">Paketmu saat ini</template>
            <template v-else>Pilih {{ p.name }}</template>
          </button>
        </article>
      </div>

      <div class="flex flex-wrap items-center justify-between gap-3 text-sm">
        <button v-if="upgrade.quota" type="button" data-test="buy-checks" class="font-semibold text-navy underline" @click="go('plans', { hash: '#pay-per-check' })">
          Beli analisis tambahan
        </button>
        <span v-else />
        <button type="button" data-test="all-plans" class="font-semibold text-navy underline" @click="go('plans')">Lihat semua paket</button>
      </div>
    </div>
  </div>
</template>
