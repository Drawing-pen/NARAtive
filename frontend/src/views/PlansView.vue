<script setup>
import SoonButton from '@/components/SoonButton.vue'
import TierChip from '@/components/TierChip.vue'

const plans = [
  {
    key: 'standard', name: 'Standard', tag: 'Gratis', current: true, icon: 'lucide:user',
    limits: ['50 halaman per unggahan', '3 analisis per bulan', '3 e-book aktif'],
    features: ['Rating dan rentang usia', 'Persentase konten dewasa dan bobot cerita', 'Mode baca dan Safe Mode standar'],
  },
  {
    key: 'middle', name: 'Middle', tag: 'Menengah', icon: 'lucide:sparkles',
    limits: ['300 halaman per unggahan', '15 analisis per bulan', '50 e-book aktif'],
    features: ['Semua fitur Standard', 'Rincian per dimensi dan alasan rating', 'Rangkuman cerita per bab', 'Biodata tokoh', 'Relasi antar tokoh'],
  },
  {
    key: 'high', name: 'High', tag: 'Lengkap', popular: true, icon: 'lucide:crown',
    limits: ['Tanpa batas halaman', 'Tanpa batas analisis', 'Tanpa batas koleksi'],
    features: ['Semua fitur Middle', 'Profil sensitivitas personal', 'Unduh hasil analisis (PDF beranotasi)'],
  },
]
</script>

<template>
  <div class="container-page space-y-12 py-12">
    <header class="max-w-2xl space-y-3">
      <p class="eyebrow">Berlangganan</p>
      <h1 class="text-4xl font-semibold sm:text-5xl">Pilih paket sesuai cara bacamu</h1>
      <p class="text-lg text-muted">Mulai gratis, naikkan tingkatan saat butuh rincian yang lebih dalam atau kuota yang lebih besar.</p>
    </header>

    <p class="flex items-start gap-2 rounded-xl bg-sand px-4 py-3 text-sm text-navy">
      <Icon icon="lucide:info" class="mt-0.5 size-4 shrink-0" />
      Halaman ini masih tampilan awal: harga belum ditetapkan, pembayaran belum aktif, dan batas paket belum diberlakukan pada versi prototipe ini.
    </p>

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
          <span v-else class="chip bg-lavender/25 text-navy"><Icon icon="lucide:check" class="size-3" />Paketmu sekarang</span>
        </div>

        <div>
          <p class="font-display text-3xl font-semibold text-navy">{{ p.key === 'standard' ? 'Gratis' : 'Segera diumumkan' }}</p>
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
          <SoonButton v-if="p.key !== 'standard'" class="w-full [&>button]:w-full" :variant="p.popular ? 'accent' : 'primary'" icon="lucide:gem">Pilih paket {{ p.name }}</SoonButton>
          <SoonButton v-else class="w-full [&>button]:w-full" variant="quiet">Paket aktif</SoonButton>
        </div>
      </article>
    </section>

    <section class="grid gap-6 lg:grid-cols-2">
      <article class="card space-y-4 p-7">
        <div class="flex items-center gap-3">
          <span class="grid size-11 place-items-center rounded-xl bg-sand text-navy"><Icon icon="lucide:zap" class="size-6" /></span>
          <h2 class="text-xl font-semibold">Analisis tambahan (pay-per-check)</h2>
        </div>
        <p class="text-sm text-muted">Kuota bulanan habis? Beli analisis tambahan tanpa perlu menaikkan tingkatan akun, khusus untuk pengguna Standard dan Middle.</p>
        <SoonButton variant="primary" small icon="lucide:shopping-cart">Beli analisis tambahan</SoonButton>
      </article>

      <article class="card space-y-4 p-7">
        <div class="flex items-center gap-3">
          <span class="grid size-11 place-items-center rounded-xl bg-sand text-navy"><Icon icon="lucide:receipt" class="size-6" /></span>
          <h2 class="text-xl font-semibold">Riwayat pembayaran</h2>
        </div>
        <div class="grid place-items-center gap-2 rounded-xl border border-dashed border-line px-4 py-6 text-center">
          <Icon icon="lucide:inbox" class="size-7 text-lavender" />
          <p class="text-sm text-muted">Belum ada transaksi. Riwayat upgrade dan pembelian analisis akan tampil di sini.</p>
        </div>
      </article>
    </section>
  </div>
</template>