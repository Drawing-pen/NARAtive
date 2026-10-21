<script setup>
import { computed } from 'vue'
import { ROLES } from '@/lib/content'
import { useCharacters } from '@/lib/characters'

const props = defineProps({ id: { type: String, required: true } })

const { doc, data, loading, missing, error, starting, start } = useCharacters(() => props.id)

const top = computed(() => Math.max(1, ...(data.value?.characters ?? []).map((c) => c.mention_count)))

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

      <section v-if="doc.status !== 'done'" class="card grid place-items-center gap-3 px-6 py-14 text-center">
        <Icon icon="lucide:hourglass" class="size-10 text-lavender" />
        <p class="max-w-md text-sm text-muted">Tokoh bisa dideteksi setelah analisis buku ini selesai.</p>
        <RouterLink :to="{ name: 'document', params: { id } }" class="btn btn-primary btn-sm">Lihat status analisis</RouterLink>
      </section>

      <section v-else-if="!data?.status" class="card grid place-items-center gap-4 px-6 py-14 text-center">
        <Icon icon="lucide:contact-round" class="size-12 text-navy" />
        <div class="space-y-1">
          <h2 class="text-2xl font-semibold">Deteksi tokoh cerita</h2>
          <p class="max-w-md text-sm text-muted">
            Sistem mengenali nama tokoh dari teks buku, menghitung seberapa sering mereka muncul, lalu menyusun biodata dan relasinya.
            Prosesnya berjalan di server dan bisa memakan waktu beberapa menit.
          </p>
        </div>
        <button class="btn btn-primary" :disabled="starting" @click="start">
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
        <button class="btn btn-primary btn-sm" :disabled="starting" @click="start">
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
        <button class="btn btn-quiet btn-sm" :disabled="starting" @click="start">
          <Icon icon="lucide:refresh-cw" class="size-4" />
          Deteksi ulang
        </button>
      </section>

      <template v-else>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <p class="text-sm text-muted">{{ data.characters.length }} tokoh terdeteksi, diurutkan dari yang paling sering disebut.</p>
          <div class="flex flex-wrap gap-2">
            <RouterLink :to="{ name: 'relations', params: { id } }" class="btn btn-primary btn-sm">
              <Icon icon="lucide:git-fork" class="size-4" />
              Lihat relasi tokoh
            </RouterLink>
            <button class="btn btn-quiet btn-sm" :disabled="starting" @click="start">
              <Icon icon="lucide:refresh-cw" class="size-4" />
              Deteksi ulang
            </button>
          </div>
        </div>

        <section class="grid gap-5 sm:grid-cols-2 lg:grid-cols-3" aria-label="Daftar tokoh">
          <article v-for="c in data.characters" :key="c.id" class="card flex flex-col gap-4 p-5">
            <div class="flex items-start gap-3">
              <span
                class="grid size-12 shrink-0 place-items-center rounded-full font-display text-lg font-semibold"
                :class="ROLES[c.role]?.avatar"
                aria-hidden="true"
              >{{ initials(c.name) }}</span>
              <div class="min-w-0 flex-1 space-y-1">
                <h2 class="truncate text-lg leading-snug font-semibold" :title="c.name">{{ c.name }}</h2>
                <span class="chip" :class="ROLES[c.role]?.chip">{{ c.role }}</span>
              </div>
            </div>
            <div class="space-y-1.5">
              <p class="text-xs font-semibold text-muted">Disebut {{ c.mention_count }} kali</p>
              <div class="h-1.5 overflow-hidden rounded-full bg-sand" aria-hidden="true">
                <div class="h-full rounded-full bg-lavender" :style="{ width: (c.mention_count / top) * 100 + '%' }" />
              </div>
            </div>
            <p class="text-sm leading-relaxed text-navy/90">{{ c.biodata }}</p>
          </article>
        </section>

        <p class="flex items-start gap-2 text-xs text-muted">
          <Icon icon="lucide:info" class="mt-0.5 size-3.5 shrink-0" />
          Tokoh dikenali otomatis dari nama yang disebut di teks, jadi hasilnya bisa keliru: misalnya nama panggilan yang belum digabung dengan nama lengkap, atau nama tempat yang terbaca sebagai tokoh.
        </p>
      </template>
    </template>
  </div>
</template>