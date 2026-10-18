<script setup>
import { RATINGS } from '@/lib/content'

const ages = { General: 'Semua umur', Teen: '13+', Mature: '17+', Explicit: '21+' }

const steps = [
  { icon: 'lucide:file-up', title: 'Unggah naskah', text: 'Pilih e-book berformat PDF atau EPUB dari perangkatmu.' },
  { icon: 'lucide:scan-search', title: 'Naskah dianalisis', text: 'Model membaca tiap paragraf dan menganalisis bahasa kasar, konten seksual, kekerasan, dan bobot ceritanya.' },
  { icon: 'lucide:book-open', title: 'Baca dengan tenang', text: 'Lihat rating dan rentang usia, lalu baca per bab dengan Safe Mode yang menyamarkan adegan sensitif.' },
]

const features = [
  { icon: 'lucide:badge-check', title: 'Rating dan rentang usia', text: 'General, Teen, Mature, atau Explicit, lengkap dengan usia pembaca yang disarankan.' },
  { icon: 'lucide:shield-alert', title: 'Persentase konten dewasa', text: 'Berapa banyak paragraf yang memuat konten dewasa atau sensitif.' },
  { icon: 'lucide:weight', title: 'Bobot cerita', text: 'Seberapa berat konflik atau teman yang diangkat di dalam cerita.' },
  { icon: 'lucide:eye-off', title: 'Safe Mode', text: 'Adegan dewasa diburamkan, dan kamu yang memutuskan mau membukanya atau tidak.' },
  { icon: 'lucide:library-big', title: 'Mode baca per bab', text: 'Baca langsung di sini tanpa aplikasi pembaca e-book, lengkap dengan navigasi bab.' },
]
</script>

<template>
  <div class="space-y-20 overflow-x-clip pb-6">
    <!-- Hero -->
    <section class="container-page grid gap-10 pt-12 lg:grid-cols-[1.1fr_1fr] lg:items-center lg:pt-16">
      <div class="space-y-6">
        <p class="eyebrow">Analisis konten e-book</p>
        <h1 class="text-4xl leading-[1.1] font-semibold sm:text-5xl">Kenali isi buku sebelum kamu membacanya.</h1>
        <p class="max-w-lg text-lg text-muted">
          NARAtive membaca e-book PDF atau EPUB-mu, menilai muatan kontennya, lalu menemanimu membaca dengan Safe Mode yang menyamarkan adegan sensitif.
        </p>
        <div class="flex flex-wrap gap-3">
          <RouterLink :to="{ name: 'library' }" class="btn btn-primary">
            <Icon icon="lucide:file-up" class="size-4.5" />
            Mulai unggah naskah
          </RouterLink>
          <RouterLink :to="{ name: 'plans' }" class="btn btn-outline">
            <Icon icon="lucide:gem" class="size-4.5" />
            Lihat paket
          </RouterLink>
        </div>
      </div>

      <!-- Contoh tampilan -->
      <div class="relative">
        <div class="pointer-events-none absolute -inset-6 rounded-[2rem] bg-amber/20 blur-3xl" />
        <div class="card relative space-y-5 p-6" aria-label="Contoh tampilan hasil analisis">
          <div class="flex items-center justify-between">
            <p class="eyebrow">Contoh hasil analisis</p>
            <span class="chip bg-sand text-navy">Ilustrasi</span>
          </div>
          <div class="flex items-center gap-3">
            <span class="font-display text-4xl font-semibold text-navy">Teen</span>
          </div>
          <div class="grid grid-cols-3 gap-3 text-center">
            <div class="rounded-xl bg-paper p-3"><p class="font-display text-2xl font-semibold text-navy">3,5%</p><p class="text-[11px] text-muted">Konten dewasa</p></div>
            <div class="rounded-xl bg-paper p-3"><p class="font-display text-2xl font-semibold text-navy">13+</p><p class="text-[11px] text-muted">Rentang Usia</p></div>
            <div class="rounded-xl bg-paper p-3"><p class="font-display text-2xl font-semibold text-navy">10</p><p class="text-[11px] text-muted">Bobot Cerita</p></div>
          </div>
          <div class="space-y-2 font-read text-[15px] leading-relaxed text-ink">
            <p>Hujan turun deras di luar. Suara petir terdengar susul-menyusul.</p>
            <div class="relative overflow-hidden rounded-lg bg-sand/70 p-3">
              <p class="blur-sm select-none" aria-hidden="true">Paragraf yang disamarkan oleh Safe Mode tampil buram seperti ini sampai diketuk.</p>
              <span class="absolute inset-0 grid place-items-center text-xs font-semibold text-navy">
                <span class="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1 shadow-sm"><Icon icon="lucide:eye" class="size-3.5" />Ketuk untuk menampilkan</span>
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Cara kerja -->
    <section class="container-page space-y-8">
      <div class="max-w-xl space-y-2">
        <p class="eyebrow">Cara kerja</p>
        <h2 class="text-3xl font-semibold">Tiga langkah, tanpa ribet</h2>
      </div>
      <ol class="grid gap-5 md:grid-cols-3">
        <li v-for="(s, i) in steps" :key="s.title" class="card relative space-y-3 p-6">
          <span class="absolute top-5 right-6 font-display text-5xl font-semibold text-sand">{{ i + 1 }}</span>
          <span class="grid size-12 place-items-center rounded-xl bg-navy text-amber"><Icon :icon="s.icon" class="size-6" /></span>
          <h3 class="text-xl font-semibold">{{ s.title }}</h3>
          <p class="text-sm text-muted">{{ s.text }}</p>
        </li>
      </ol>
    </section>

    <!-- Kategori rating -->
    <section class="container-page space-y-8">
      <div class="max-w-xl space-y-2">
        <p class="eyebrow">Kategori rating</p>
        <h2 class="text-3xl font-semibold">Empat kategori, satu panduan usia</h2>
      </div>
      <ul class="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <li v-for="(r, key) in RATINGS" :key="key" class="card space-y-3 p-5">
          <span class="chip" :class="r.cls"><Icon :icon="r.icon" class="size-3.5" />{{ r.label }}</span>
          <p class="font-display text-3xl font-semibold text-navy">{{ ages[key] }}</p>
          <p class="text-sm text-muted">{{ r.note }}</p>
        </li>
      </ul>
    </section>

    <!-- Fitur -->
    <section class="container-page space-y-8">
      <div class="max-w-xl space-y-2">
        <p class="eyebrow">Yang kamu dapatkan</p>
        <h2 class="text-3xl font-semibold">Dari rating sampai mode baca</h2>
      </div>
      <ul class="grid gap-x-8 gap-y-7 sm:grid-cols-2 lg:grid-cols-3">
        <li v-for="f in features" :key="f.title" class="flex gap-4">
          <span class="grid size-11 shrink-0 place-items-center rounded-xl bg-sand text-navy"><Icon :icon="f.icon" class="size-6" /></span>
          <div class="space-y-1">
            <h3 class="text-lg font-semibold">{{ f.title }}</h3>
            <p class="text-sm text-muted">{{ f.text }}</p>
          </div>
        </li>
      </ul>
      <p class="flex items-start gap-2 text-xs text-muted">
        <Icon icon="lucide:info" class="mt-0.5 size-3.5 shrink-0" />
        Rating adalah prediksi sistem berbasis model bahasa, dipakai sebagai panduan awal dan bukan keputusan akhir.
      </p>
    </section>

    <!-- Ajakan -->
    <section class="container-page">
      <div class="flex flex-col gap-5 rounded-2xl bg-navy p-8 sm:flex-row sm:items-center sm:justify-between sm:p-10">
        <div>
          <h2 class="text-3xl font-semibold text-white">Mulai dari satu e-book</h2>
          <p class="mt-1 text-white/70">Unggah naskah pertamamu dan lihat hasilnya.</p>
        </div>
        <RouterLink :to="{ name: 'library' }" class="btn btn-accent shrink-0">
          <Icon icon="lucide:file-up" class="size-4.5" />
          Ke koleksi
        </RouterLink>
      </div>
    </section>
  </div>
</template>