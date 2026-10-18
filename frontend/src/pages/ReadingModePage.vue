<script setup>
import SoonButton from '@/components/SoonButton.vue'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import api, { errorMessage } from '@/lib/api'
import { DIMENSIONS, STANDARD_THRESHOLDS } from '@/lib/content'

const props = defineProps({ id: { type: String, required: true } })

const SETTINGS_KEY = 'narative_reader'
const FONT_SIZES = ['text-[15px]', 'text-base', 'text-[17px]', 'text-lg', 'text-xl']

function loadSettings() {
  try {
    return JSON.parse(localStorage.getItem(SETTINGS_KEY)) ?? {}
  } catch {
    return {}
  }
}
const saved = loadSettings()

const doc = ref(null)
const chapters = ref([])
const paragraphs = ref([])
const loading = ref(true)
const error = ref('')
const progress = ref(0)

const chapterNo = ref(1)
const safeMode = ref(saved.safeMode ?? true)
const fontStep = ref(saved.fontStep ?? 2)
const serif = ref(saved.serif ?? true)
const revealed = reactive(new Set())

function persist() {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify({ safeMode: safeMode.value, fontStep: fontStep.value, serif: serif.value }))
  } catch {
    /* penyimpanan browser tidak tersedia, abaikan */
  }
}

const SAFE_MODE_DIMENSIONS = ['sexual']
function flagsOf(p) {
  return SAFE_MODE_DIMENSIONS.filter((key) => p[key] !== null && p[key] >= STANDARD_THRESHOLDS[key])
}
const isHidden = (p) => safeMode.value && flagsOf(p).length > 0 && !revealed.has(p.idx)

const chapter = computed(() => chapters.value.find((c) => c.number === chapterNo.value))
const chapterParagraphs = computed(() => paragraphs.value.filter((p) => p.chapter_no === chapterNo.value))
const isRevealedFlag = (p) => safeMode.value && flagsOf(p).length > 0 && revealed.has(p.idx)
const revealedCount = computed(() => chapterParagraphs.value.filter(isRevealedFlag).length)
const hiddenCount = computed(() => chapterParagraphs.value.filter(isHidden).length)
const firstVisible = computed(() => chapterParagraphs.value.find((p) => !isHidden(p))?.idx)
const hasPrev = computed(() => chapterNo.value > 1)
const hasNext = computed(() => chapterNo.value < chapters.value.length)

function toggleSafeMode() {
  safeMode.value = !safeMode.value
  revealed.clear()
  persist()
}
function goChapter(n) {
  if (n < 1 || n > chapters.value.length) return
  chapterNo.value = n
  window.scrollTo({ top: 0 })
}
function step(delta) {
  fontStep.value = Math.min(FONT_SIZES.length - 1, Math.max(0, fontStep.value + delta))
  persist()
}
function onScroll() {
  const max = document.documentElement.scrollHeight - window.innerHeight
  progress.value = max > 0 ? Math.min(100, (window.scrollY / max) * 100) : 0
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [d, c, p] = await Promise.all([
      api.get(`/documents/${props.id}`),
      api.get(`/documents/${props.id}/chapters`),
      api.get(`/documents/${props.id}/paragraphs`),
    ])
    doc.value = d.data
    chapters.value = c.data
    paragraphs.value = p.data
  } catch (e) {
    error.value = e.response?.status === 404 ? 'Dokumen tidak ditemukan.' : errorMessage(e, 'Gagal memuat teks e-book.')
  } finally {
    loading.value = false
  }
}

watch(chapterNo, () => revealed.clear())
onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
  load()
})
onBeforeUnmount(() => window.removeEventListener('scroll', onScroll))
</script>

<template>
  <div class="min-h-screen">
    <!-- Bilah atas -->
    <header class="sticky top-0 z-30 border-b border-line bg-paper/90 backdrop-blur">
      <div class="container-page flex items-center gap-3 py-2.5">
        <div class="min-w-0 flex-1">
          <p class="truncate font-display text-base font-semibold text-navy sm:text-lg">{{ doc?.title ?? 'Mode baca' }}</p>
          <p v-if="doc && doc.status === 'done'" class="eyebrow truncate !text-[10px]">
            {{ safeMode ? (hiddenCount ? `${hiddenCount} paragraf disamarkan di bab ini` : 'Safe Mode aktif · tidak ada paragraf disamarkan di bab ini') : 'Safe Mode nonaktif' }}
          </p>
        </div>

        <div class="flex items-center gap-1.5">
          <div class="hidden items-center rounded-lg bg-sand sm:flex">
            <button class="grid size-9 place-items-center rounded-l-lg text-navy transition hover:bg-line disabled:opacity-40" :disabled="fontStep === 0" aria-label="Perkecil huruf" @click="step(-1)">
              <Icon icon="lucide:a-arrow-down" class="size-5" />
            </button>
            <button class="grid size-9 place-items-center rounded-r-lg text-navy transition hover:bg-line disabled:opacity-40" :disabled="fontStep === FONT_SIZES.length - 1" aria-label="Perbesar huruf" @click="step(1)">
              <Icon icon="lucide:a-arrow-up" class="size-5" />
            </button>
          </div>
          <button class="grid size-9 place-items-center rounded-lg bg-sand text-navy transition hover:bg-line" :aria-label="serif ? 'Ganti ke huruf tanpa serif' : 'Ganti ke huruf serif'" @click="serif = !serif; persist()">
            <Icon :icon="serif ? 'lucide:type' : 'lucide:case-sensitive'" class="size-5" />
          </button>
          <SoonButton class="hidden md:inline-flex" variant="outline" small tier="high" icon="lucide:sliders-horizontal">Sensitivitas</SoonButton>
          <button v-if="revealedCount" class="btn btn-quiet btn-sm" title="Samarkan kembali semua paragraf yang sudah dibuka di bab ini" @click="revealed.clear()">
            <Icon icon="lucide:eye-off" class="size-4" />
            <span class="hidden sm:inline">Samarkan lagi ({{ revealedCount }})</span>
          </button>
          <button class="btn btn-sm" :class="safeMode ? 'btn-accent' : 'btn-quiet'" :aria-pressed="safeMode" @click="toggleSafeMode">
            <Icon :icon="safeMode ? 'lucide:shield-check' : 'lucide:shield-off'" class="size-4" />
            <span class="hidden sm:inline">Safe Mode {{ safeMode ? 'aktif' : 'nonaktif' }}</span>
          </button>
        </div>
      </div>
      <div class="h-0.5 bg-transparent"><div class="h-full bg-amber transition-[width] duration-150" :style="{ width: progress + '%' }" /></div>
    </header>

    <!-- Naskah -->
    <main class="container-page py-10">
      <div v-if="loading" class="flex items-center justify-center gap-2 py-24 text-muted">
        <Icon icon="lucide:loader-circle" class="size-5 animate-spin" />
        Menyiapkan naskah…
      </div>

      <div v-else-if="error" class="card mx-auto grid max-w-md place-items-center gap-3 px-6 py-12 text-center">
        <Icon icon="lucide:circle-alert" class="size-10 text-danger" />
        <p class="text-sm text-muted">{{ error }}</p>
        <button class="btn btn-primary btn-sm" @click="load">
          <Icon icon="lucide:refresh-cw" class="size-4" />
          Coba lagi
        </button>
      </div>

      <div v-else-if="doc && doc.status !== 'done'" class="card mx-auto grid max-w-md place-items-center gap-3 px-6 py-12 text-center">
        <Icon icon="lucide:scan-search" class="size-10 text-lavender" />
        <p class="font-display text-lg text-navy">E-book ini belum selesai dianalisis</p>
        <p class="text-sm text-muted">Mode baca tersedia setelah analisis selesai.</p>
        <RouterLink :to="{ name: 'document', params: { id } }" class="btn btn-accent btn-sm">Lihat status analisis</RouterLink>
      </div>

      <article v-else class="card mx-auto max-w-3xl px-6 py-10 sm:px-14 sm:py-14">
        <!-- Navigasi bab -->
        <nav class="mb-8 flex items-center justify-between gap-3" aria-label="Navigasi bab">
          <button class="btn btn-quiet btn-sm" :disabled="!hasPrev" @click="goChapter(chapterNo - 1)">
            <Icon icon="lucide:chevron-left" class="size-4" />
            <span class="hidden sm:inline">Bab sebelumnya</span>
          </button>
          <label class="relative min-w-0 flex-1">
            <span class="sr-only">Pilih bab</span>
            <select
              :value="chapterNo"
              class="w-full appearance-none truncate rounded-lg border border-line bg-paper py-2 pr-9 pl-3 text-center font-sans text-sm font-semibold text-navy focus:border-lavender focus:outline-none"
              @change="goChapter(Number($event.target.value))"
            >
              <option v-for="c in chapters" :key="c.number" :value="c.number">{{ c.title }}</option>
            </select>
            <Icon icon="lucide:chevrons-up-down" class="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted" />
          </label>
          <button class="btn btn-quiet btn-sm" :disabled="!hasNext" @click="goChapter(chapterNo + 1)">
            <span class="hidden sm:inline">Bab berikutnya</span>
            <Icon icon="lucide:chevron-right" class="size-4" />
          </button>
        </nav>

        <header class="mb-10 space-y-4 text-center">
          <p class="flex items-center justify-center gap-3 text-[11px] font-semibold tracking-[0.2em] text-amber uppercase">
            <span class="h-px w-10 bg-amber/60" />
            Bab {{ chapterNo }} dari {{ chapters.length }}
            <span class="h-px w-10 bg-amber/60" />
          </p>
          <h1 class="text-3xl leading-tight font-semibold sm:text-4xl">{{ chapter?.title ?? doc.title }}</h1>
          <Icon icon="lucide:asterisk" class="mx-auto size-5 text-lavender" />
        </header>

        <div class="space-y-5 leading-[1.95] text-ink" :class="[FONT_SIZES[fontStep], serif ? 'font-read' : 'font-sans']">
          <template v-for="p in chapterParagraphs" :key="p.idx">
            <button
              v-if="isHidden(p)"
              type="button"
              class="para group relative block min-h-44 w-full cursor-pointer overflow-hidden rounded-xl text-left"
              aria-label="Paragraf seksual disamarkan. Ketuk untuk menampilkan."
              @click="revealed.add(p.idx)"
            >
              <span class="block px-1 blur-md select-none" aria-hidden="true">{{ p.text }}</span>
              <span class="absolute inset-0 grid place-items-center bg-paper/40 p-3 font-sans transition group-hover:bg-paper/20">
                <span class="flex max-w-full flex-col items-center gap-2 rounded-xl bg-white/90 px-4 py-3 text-center shadow-sm">
                  <span class="flex items-center gap-2 text-sm font-semibold text-navy">
                    <Icon icon="lucide:shield-check" class="size-4.5 text-danger" />
                    Adegan seksual disamarkan
                  </span>
                  <span class="flex flex-wrap justify-center gap-1.5">
                    <span v-for="key in flagsOf(p)" :key="key" class="chip bg-sand text-navy">
                      <Icon :icon="DIMENSIONS[key].icon" class="size-3.5" />
                      {{ DIMENSIONS[key].label }}
                    </span>
                  </span>
                  <span class="flex items-center gap-1.5 text-xs font-semibold text-muted">
                    <Icon icon="lucide:eye" class="size-3.5" />
                    Ketuk untuk menampilkan
                  </span>
                </span>
              </span>
            </button>

            <div v-else-if="isRevealedFlag(p)" class="para relative -mx-3 rounded-xl bg-amber/10 px-3 pt-9 pb-3 ring-1 ring-amber/40">
              <button
                type="button"
                class="absolute top-2 right-2 inline-flex items-center gap-1.5 rounded-lg bg-white px-2.5 py-1 font-sans text-xs font-semibold text-navy shadow-sm transition hover:bg-sand"
                aria-label="Samarkan kembali paragraf ini"
                @click="revealed.delete(p.idx)"
              >
                <Icon icon="lucide:eye-off" class="size-3.5" />
                Samarkan lagi
              </button>
              <p class="whitespace-pre-line">{{ p.text }}</p>
            </div>

            <p v-else class="para whitespace-pre-line" :class="{ 'drop-cap': p.idx === firstVisible }">{{ p.text }}</p>
          </template>
        </div>

        <footer class="mt-12 flex items-center justify-between gap-3 border-t border-line pt-6">
          <button class="btn btn-quiet btn-sm" :disabled="!hasPrev" @click="goChapter(chapterNo - 1)">
            <Icon icon="lucide:chevron-left" class="size-4" />
            Sebelumnya
          </button>
          <RouterLink v-if="!hasNext" :to="{ name: 'document', params: { id } }" class="btn btn-accent btn-sm">
            <Icon icon="lucide:chart-no-axes-column" class="size-4" />
            Selesai, lihat hasil
          </RouterLink>
          <button v-else class="btn btn-primary btn-sm" @click="goChapter(chapterNo + 1)">
            Bab berikutnya
            <Icon icon="lucide:chevron-right" class="size-4" />
          </button>
        </footer>
      </article>
    </main>
  </div>
</template>