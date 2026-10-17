<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import api, { errorMessage } from '@/lib/api'

// UC-09: rangkuman per bab dan keseluruhan buku
const props = defineProps({ id: { type: String, required: true } })

const doc = ref(null)
const sum = ref(null)
const loading = ref(true)
const missing = ref(false)
const error = ref('')
const starting = ref(false)
let timer = null

async function load(silent = false) {
  try {
    const [d, s] = await Promise.all([api.get(`/documents/${props.id}`), api.get(`/documents/${props.id}/summary`)])
    doc.value = d.data
    sum.value = s.data
    error.value = ''
  } catch (e) {
    if (e.response?.status === 404) missing.value = true
    else if (!silent) error.value = errorMessage(e, 'Gagal mengambil rangkuman.')
  } finally {
    loading.value = false
  }
}

async function start() {
  starting.value = true
  error.value = ''
  try {
    const { data } = await api.post(`/documents/${props.id}/summary`)
    sum.value = data
  } catch (e) {
    error.value = errorMessage(e, 'Gagal memulai pembuatan rangkuman.')
  } finally {
    starting.value = false
  }
}

onMounted(() => {
  load()
  timer = setInterval(() => {
    if (sum.value?.status === 'running') load(true)
  }, 3000)
})
onBeforeUnmount(() => clearInterval(timer))
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
        <p class="eyebrow">Rangkuman cerita</p>
        <h1 class="text-3xl leading-tight font-semibold break-words sm:text-4xl">{{ doc.title }}</h1>
      </section>

      <p v-if="error" role="alert" class="flex items-start gap-2 rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">
        <Icon icon="lucide:circle-alert" class="mt-0.5 size-4 shrink-0" />
        {{ error }}
      </p>

      <!-- Analisis belum selesai -->
      <section v-if="doc.status !== 'done'" class="card grid place-items-center gap-3 px-6 py-14 text-center">
        <Icon icon="lucide:hourglass" class="size-10 text-lavender" />
        <p class="max-w-md text-sm text-muted">Rangkuman bisa dibuat setelah analisis buku ini selesai.</p>
        <RouterLink :to="{ name: 'document', params: { id } }" class="btn btn-primary btn-sm">Lihat status analisis</RouterLink>
      </section>

      <!-- Belum pernah dibuat -->
      <section v-else-if="!sum?.status" class="card grid place-items-center gap-4 px-6 py-14 text-center">
        <Icon icon="lucide:scroll-text" class="size-12 text-navy" />
        <div class="space-y-1">
          <h2 class="text-2xl font-semibold">Buat rangkuman cerita</h2>
          <p class="max-w-md text-sm text-muted">
            Sistem merangkum {{ sum?.total_chapters }} bab satu per satu, lalu menyusun rangkuman seluruh buku.
            Teks buku dikirim ke layanan Gemini untuk diringkas, dan prosesnya bisa beberapa menit.
          </p>
        </div>
        <button class="btn btn-primary" :disabled="starting" @click="start">
          <Icon :icon="starting ? 'lucide:loader-circle' : 'lucide:sparkles'" class="size-4.5" :class="{ 'animate-spin': starting }" />
          Buat rangkuman
        </button>
      </section>

      <!-- Sedang dibuat -->
      <section v-else-if="sum.status === 'running'" class="card grid place-items-center gap-4 px-6 py-16 text-center">
        <Icon icon="lucide:loader-circle" class="size-12 animate-spin text-navy" />
        <div class="space-y-1">
          <h2 class="text-2xl font-semibold">Sedang membuat rangkuman</h2>
          <p class="max-w-md text-sm text-muted">
            {{ sum.done_chapters }} dari {{ sum.total_chapters }} bab selesai. Halaman ini memperbarui diri otomatis.
          </p>
        </div>
        <div class="h-2 w-full max-w-xs overflow-hidden rounded-full bg-sand">
          <div class="h-full rounded-full bg-navy transition-all" :style="{ width: (sum.total_chapters ? (sum.done_chapters / sum.total_chapters) * 100 : 0) + '%' }" />
        </div>
      </section>

      <!-- Gagal -->
      <section v-else-if="sum.status === 'failed'" class="card grid place-items-center gap-4 px-6 py-14 text-center">
        <Icon icon="lucide:circle-x" class="size-12 text-danger" />
        <div class="space-y-1">
          <h2 class="text-2xl font-semibold">Rangkuman gagal dibuat</h2>
          <p class="max-w-md text-sm text-muted">Layanan rangkuman tidak merespons atau kunci Gemini di server belum benar. Coba lagi sebentar lagi.</p>
        </div>
        <button class="btn btn-primary btn-sm" :disabled="starting" @click="start">
          <Icon icon="lucide:refresh-cw" class="size-4" />
          Coba lagi
        </button>
      </section>

      <!-- Selesai -->
      <template v-else>
        <section class="card space-y-3 p-6 sm:p-8">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p class="eyebrow">Keseluruhan buku</p>
              <h2 class="text-xl font-semibold">Ringkasan cerita</h2>
            </div>
            <button class="btn btn-quiet btn-sm" :disabled="starting" @click="start">
              <Icon icon="lucide:refresh-cw" class="size-4" />
              Buat ulang
            </button>
          </div>
          <p class="text-[15px] leading-relaxed whitespace-pre-line text-navy">{{ sum.overall }}</p>
        </section>

        <section class="space-y-3" aria-labelledby="per-bab">
          <h2 id="per-bab" class="text-xl font-semibold">Rangkuman per bab</h2>
          <article v-for="c in sum.chapters" :key="c.number" class="card space-y-2 p-5 sm:p-6">
            <p class="text-xs font-semibold tracking-wide text-muted uppercase">Bab {{ c.number }}</p>
            <h3 class="text-lg font-semibold">{{ c.title }}</h3>
            <p class="text-[15px] leading-relaxed whitespace-pre-line text-navy/90">{{ c.summary }}</p>
          </article>
        </section>

        <p class="flex items-start gap-2 text-xs text-muted">
          <Icon icon="lucide:info" class="mt-0.5 size-3.5 shrink-0" />
          Rangkuman dibuat oleh model bahasa generatif dan bisa melewatkan detail. Adegan sensitif disebut secara umum.
        </p>
      </template>
    </template>
  </div>
</template>