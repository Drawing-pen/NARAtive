<script setup>
import { computed } from 'vue'
import { hasTier } from '@/lib/auth'
import { ROLES } from '@/lib/content'
import AuthImage from '@/components/AuthImage.vue'
import PictureControls from '@/components/PictureControls.vue'
import TierLock from '@/components/TierLock.vue'
import { useCharacters } from '@/lib/characters'

const props = defineProps({ id: { type: String, required: true } })

const { doc, data, loading, missing, error, locked, starting, start } = useCharacters(() => props.id)
const canCreate = computed(() => hasTier('middle'))

const FIELDS = [
  ['gender', 'Jenis kelamin'],
  ['age', 'Usia'],
  ['occupation', 'Pekerjaan'],
  ['personality', 'Kepribadian'],
  ['background', 'Latar belakang'],
]

const hasProfile = computed(() => (data.value?.characters ?? []).some((c) => c.personality))

function photoChanged(c, has) {
  c.has_photo = has
  c.photoVersion = (c.photoVersion ?? 0) + 1
}

function facts(c) {
  return FIELDS.filter(([key]) => c[key] && c[key] !== 'Tidak disebutkan')
}

function initials(name) {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join('')
}
</script>

<template>
  <div class="container-page space-y-8 py-10">
    <div v-if="loading" class="flex items-center justify-center gap-2 py-24 text-muted">
      <Icon icon="lucide:loader-circle" class="size-5 animate-spin" />
      Memuat…
    </div>

    <div v-else-if="missing" class="card grid place-items-center gap-3 px-6 py-16 text-center">
      <Icon icon="lucide:file-x" class="size-10 text-lavender" />
      <p class="font-display text-lg text-navy">Dokumen tidak ditemukan</p>
      <RouterLink :to="{ name: 'library' }" class="btn btn-primary btn-sm">Ke koleksi</RouterLink>
    </div>

    <template v-else-if="doc">
      <section class="space-y-2">
        <p class="eyebrow">Biodata tokoh</p>
        <h1 class="text-3xl leading-tight font-semibold break-words sm:text-4xl">{{ doc.title }}</h1>
      </section>

      <p v-if="error" role="alert" class="flex items-start gap-2 rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">
        <Icon icon="lucide:circle-alert" class="mt-0.5 size-4 shrink-0" />
        {{ error }}
      </p>

      <TierLock
        v-if="locked"
        tier="middle"
        title="Fitur khusus Middle Tier"
        text="Deteksi tokoh dan relasi tersedia untuk pengguna Middle Tier ke atas. Hasil yang sudah pernah dibuat tetap bisa dilihat."
      />

      <section v-else-if="doc.status !== 'done'" class="card grid place-items-center gap-3 px-6 py-14 text-center">
        <Icon icon="lucide:hourglass" class="size-10 text-lavender" />
        <p class="max-w-md text-sm text-muted">Tokoh bisa dideteksi setelah analisis buku ini selesai.</p>
        <RouterLink :to="{ name: 'document', params: { id } }" class="btn btn-primary btn-sm">Lihat status analisis</RouterLink>
      </section>

      <section v-else-if="!data?.status" class="card grid place-items-center gap-4 px-6 py-14 text-center">
        <Icon icon="lucide:contact-round" class="size-12 text-navy" />
        <div class="space-y-1">
          <h2 class="text-2xl font-semibold">Deteksi tokoh cerita</h2>
          <p class="max-w-md text-sm text-muted">
            Sistem mengenali nama tokoh dari teks buku, menggabungkan nama panggilan yang merujuk ke orang yang sama, lalu menyusun biodata dan relasinya.
            Prosesnya berjalan di server dan bisa memakan waktu beberapa menit.
          </p>
        </div>
        <button v-if="canCreate" class="btn btn-primary" :disabled="starting" @click="start(false)">
          <Icon :icon="starting ? 'lucide:loader-circle' : 'lucide:scan-search'" class="size-4.5" :class="{ 'animate-spin': starting }" />
          Deteksi tokoh
        </button>
      </section>

      <section v-else-if="data.status === 'running'" class="card grid place-items-center gap-4 px-6 py-16 text-center">
        <Icon icon="lucide:loader-circle" class="size-12 animate-spin text-navy" />
        <div class="space-y-1">
          <h2 class="text-2xl font-semibold">Sedang mendeteksi tokoh</h2>
          <p class="max-w-md text-sm text-muted">Halaman ini memperbarui diri otomatis saat hasilnya siap.</p>
        </div>
      </section>

      <section v-else-if="data.status === 'failed'" class="card grid place-items-center gap-4 px-6 py-14 text-center">
        <Icon icon="lucide:circle-x" class="size-12 text-danger" />
        <div class="space-y-1">
          <h2 class="text-2xl font-semibold">Tokoh gagal dideteksi</h2>
          <p class="max-w-md text-sm text-muted">Model pengenal nama belum terpasang di server atau tidak bisa diunduh. Coba lagi sebentar lagi.</p>
        </div>
        <button v-if="canCreate" class="btn btn-primary btn-sm" :disabled="starting" @click="start(false)">
          <Icon icon="lucide:refresh-cw" class="size-4" />
          Coba lagi
        </button>
      </section>

      <section v-else-if="!data.characters.length" class="card grid place-items-center gap-4 px-6 py-14 text-center">
        <Icon icon="lucide:user-x" class="size-12 text-lavender" />
        <div class="space-y-1">
          <h2 class="text-2xl font-semibold">Tokoh tidak terdeteksi</h2>
          <p class="max-w-md text-sm text-muted">Sistem tidak menemukan nama tokoh yang cukup sering disebut di buku ini.</p>
        </div>
        <button v-if="canCreate" class="btn btn-quiet btn-sm" :disabled="starting" @click="start(false)">
          <Icon icon="lucide:refresh-cw" class="size-4" />
          Deteksi ulang
        </button>
      </section>

      <template v-else>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <p class="text-sm text-muted">{{ data.characters.length }} tokoh terdeteksi, diurutkan dari yang paling berperan dalam cerita.</p>
          <div class="flex flex-wrap gap-2">
            <RouterLink :to="{ name: 'relations', params: { id } }" class="btn btn-primary btn-sm">
              <Icon icon="lucide:git-fork" class="size-4" />
              Lihat relasi tokoh
            </RouterLink>
            <button v-if="canCreate" class="btn btn-quiet btn-sm" :disabled="starting" title="Menggunakan 1 permintaan Gemini" @click="start(true)">
              <Icon icon="lucide:sparkles" class="size-4" />
              {{ hasProfile ? 'Perbarui biodata AI' : 'Lengkapi biodata dengan AI' }}
            </button>
            <button v-if="canCreate" class="btn btn-quiet btn-sm" :disabled="starting" @click="start(false)">
              <Icon icon="lucide:refresh-cw" class="size-4" />
              Deteksi ulang
            </button>
          </div>
        </div>

        <p v-if="data.status === 'partial'" role="status" class="flex items-start gap-2 rounded-lg bg-sand px-3 py-2.5 text-sm text-navy">
          <Icon icon="lucide:triangle-alert" class="mt-0.5 size-4 shrink-0" />
          Biodata AI belum berhasil dibuat, kemungkinan kuota Gemini sedang habis. Coba lagi nanti.
        </p>
        <p v-else-if="!hasProfile" class="flex items-start gap-2 text-sm text-muted">
          <Icon icon="lucide:sparkles" class="mt-0.5 size-4 shrink-0" />
          Jenis kelamin, usia, dan pekerjaan diambil otomatis dari teks bila disebutkan. Tekan “Lengkapi biodata dengan AI” untuk menambah kepribadian, latar belakang, dan menggabungkan nama panggilan yang lebih rumit (memakai 1 permintaan Gemini).
        </p>

        <section class="grid gap-5 sm:grid-cols-2 lg:grid-cols-3" aria-label="Daftar tokoh">
          <article v-for="c in data.characters" :key="c.id" class="card flex flex-col gap-4 p-5">
            <div class="flex items-start gap-3">
              <span
                class="grid size-12 shrink-0 place-items-center overflow-hidden rounded-full font-display text-lg font-semibold"
                :class="ROLES[c.role]?.avatar"
                :aria-hidden="!c.has_photo"
              >
                <AuthImage :path="`/documents/${id}/characters/${c.id}/photo`" :active="c.has_photo" :version="c.photoVersion ?? 0" :alt="`Foto ${c.name}`">{{ initials(c.name) }}</AuthImage>
              </span>
              <div class="min-w-0 flex-1 space-y-1">
                <h2 class="truncate text-lg leading-snug font-semibold" :title="c.name">{{ c.name }}</h2>
                <span class="chip" :class="ROLES[c.role]?.chip">{{ c.role }}</span>
              </div>
            </div>
            <p v-if="c.aliases" class="text-xs text-muted">Juga disebut: {{ c.aliases }}</p>
            <p class="text-sm leading-relaxed text-navy/90">{{ c.biodata }}</p>
            <dl v-if="facts(c).length" class="space-y-2 border-t border-sand pt-3 text-sm">
              <div v-for="[key, label] in facts(c)" :key="key">
                <dt class="text-xs font-semibold text-muted">{{ label }}</dt>
                <dd class="leading-snug text-navy/90">{{ c[key] }}</dd>
              </div>
            </dl>
            <PictureControls
              class="mt-auto"
              :path="`/documents/${id}/characters/${c.id}/photo`"
              :has-picture="c.has_photo"
              label="Ganti foto"
              @changed="photoChanged(c, $event)"
            />
          </article>
        </section>

        <p class="flex items-start gap-2 text-xs text-muted">
          <Icon icon="lucide:info" class="mt-0.5 size-3.5 shrink-0" />
          Tokoh dikenali otomatis dari nama di teks dan biodatanya disusun AI dari kutipan cerita, jadi bisa keliru: misalnya dua tokoh yang tergabung atau terpisah, atau nama tempat yang terbaca sebagai tokoh. Rincian yang tidak disebutkan di cerita tidak ditampilkan.
        </p>
      </template>
    </template>
  </div>
</template>