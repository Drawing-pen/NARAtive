<script setup>
import { computed, onBeforeUnmount, onMounted, ref, nextTick, watch } from 'vue'
import api from '@/lib/api'
import { hasTier } from '@/lib/auth'
import TierLock from '@/components/TierLock.vue'
import NotNovelNotice from '@/components/NotNovelNotice.vue'
import ProgressLoader from '@/components/ProgressLoader.vue'
import { LOADING_TIPS, RELATION_TYPES, initials, relationType } from '@/lib/content'
import { useCharacters } from '@/lib/characters'

const props = defineProps({ id: { type: String, required: true } })

const { doc, data, loading, missing, error, locked, starting, start } = useCharacters(() => props.id)
const canCreate = computed(() => hasTier('middle'))

const chapters = ref([])
const pos = ref(null)
const hover = ref(null)
const selectedId = ref(null)
const playing = ref(false)
const photos = ref({})
let timer = null

onMounted(async () => {
  try {
    chapters.value = (await api.get(`/documents/${props.id}/chapters`)).data
  } catch {
    chapters.value = []
  }
})

function centerScroll(el) {
  if (el) nextTick(() => { el.scrollLeft = (el.scrollWidth - el.clientWidth) / 2 })
}

const W = 760
const H = 560
const CX = W / 2
const CY = H / 2
const RING = 190
const STEP_MS = 1200

const characters = computed(() => data.value?.characters ?? [])
const byId = computed(() => new Map(characters.value.map((c) => [c.id, c])))
const maxMentions = computed(() => Math.max(1, ...characters.value.map((c) => c.mention_count)))
const relations = computed(() => data.value?.relations ?? [])

const numbers = computed(() =>
  chapters.value.length ? chapters.value.map((c) => c.number) : [...new Set(relations.value.map((r) => r.chapter))].sort((x, y) => x - y),
)
const last = computed(() => Math.max(0, numbers.value.length - 1))
const current = computed(() => Math.min(pos.value ?? last.value, last.value))
const chapterNumber = computed(() => numbers.value[current.value] ?? 0)
const atEnd = computed(() => current.value >= last.value)

const chapterLabel = computed(() => {
  const c = chapters.value.find((x) => x.number === chapterNumber.value)
  if (!c) return `Bab ${chapterNumber.value}`
  return `Bab ${c.number} · ${c.title.length > 42 ? c.title.slice(0, 42) + '…' : c.title}`
})

function stop() {
  playing.value = false
  clearInterval(timer)
  timer = null
}

function slideTo(value) {
  stop()
  pos.value = Math.max(0, Math.min(last.value, value))
}

function togglePlay() {
  if (playing.value) return stop()
  if (atEnd.value) pos.value = 0
  playing.value = true
  timer = setInterval(() => {
    if (current.value < last.value) pos.value = current.value + 1
    if (current.value >= last.value) stop()
  }, STEP_MS)
}

onBeforeUnmount(() => {
  stop()
  Object.values(photos.value).forEach((u) => URL.revokeObjectURL(u))
})

function mergeUpTo(limit) {
  const merged = new Map()
  for (const r of relations.value) {
    if (r.chapter > limit) continue
    const key = `${r.a}-${r.b}`
    const cur = merged.get(key) ?? { key, a: r.a, b: r.b, weight: 0, kinds: new Map() }
    cur.weight += r.weight
    const kind = relationType(r.type).key
    cur.kinds.set(kind, (cur.kinds.get(kind) ?? 0) + r.weight)
    merged.set(key, cur)
  }
  return new Map(
    [...merged].map(([key, { kinds, ...e }]) => {
      const known = [...kinds].filter(([k]) => k !== 'kenalan')
      const pool = known.length ? known : [...kinds]
      return [key, { ...e, type: pool.sort((x, y) => y[1] - x[1])[0][0] }]
    }),
  )
}

const whole = computed(() => mergeUpTo(Infinity))
const upTo = computed(() => mergeUpTo(chapterNumber.value))
const edges = computed(() => [...upTo.value.values()])

const legend = computed(() => {
  const present = new Set(edges.value.map((e) => relationType(e.type).key))
  return Object.entries(RELATION_TYPES).filter(([key]) => present.has(key))
})

const maxWeight = computed(() => Math.max(1, ...[...whole.value.values()].map((e) => e.weight)))

const degreeNow = computed(() => {
  const degree = new Map()
  for (const e of edges.value) {
    degree.set(e.a, (degree.get(e.a) ?? 0) + e.weight)
    degree.set(e.b, (degree.get(e.b) ?? 0) + e.weight)
  }
  return degree
})

const nodes = computed(() => {
  const degree = new Map()
  for (const e of whole.value.values()) {
    degree.set(e.a, (degree.get(e.a) ?? 0) + e.weight)
    degree.set(e.b, (degree.get(e.b) ?? 0) + e.weight)
  }
  const ids = [...degree.keys()].filter((id) => byId.value.has(id)).sort((x, y) => degree.get(y) - degree.get(x))
  return ids.map((id, i) => {
    const c = byId.value.get(id)
    const angle = -Math.PI / 2 + (2 * Math.PI * i) / ids.length
    const r = 15 + 13 * (c.mention_count / maxMentions.value)
    const x = CX + RING * Math.cos(angle)
    const y = CY + RING * Math.sin(angle)
    const cos = Math.cos(angle)
    return {
      id,
      name: c.name,
      x,
      y,
      r,
      lx: x + (r + 8) * cos,
      ly: y + (r + 8) * Math.sin(angle) + 4,
      anchor: cos > 0.15 ? 'start' : cos < -0.15 ? 'end' : 'middle',
      present: degreeNow.value.has(id),
    }
  })
})

const nodeById = computed(() => new Map(nodes.value.map((n) => [n.id, n])))
const presentCount = computed(() => nodes.value.filter((n) => n.present).length)

const drawn = computed(() =>
  [...whole.value.values()]
    .filter((e) => nodeById.value.has(e.a) && nodeById.value.has(e.b))
    .map((e) => {
      const now = upTo.value.get(e.key)
      const shown = now ?? e
      return {
        key: e.key,
        a: e.a,
        b: e.b,
        weight: now?.weight ?? 0,
        type: shown.type,
        p: nodeById.value.get(e.a),
        q: nodeById.value.get(e.b),
        width: now ? 1.5 + (6 * now.weight) / maxWeight.value : 0,
      }
    }),
)

const listed = computed(() => [...edges.value].sort((x, y) => y.weight - x.weight))

const focusId = computed(() => selectedId.value ?? hover.value)

function edgeOpacity(e) {
  if (!e.weight) return 0
  if (focusId.value === null) return 0.7
  return e.a === focusId.value || e.b === focusId.value ? 1 : 0.08
}

function nodeOpacity(n) {
  if (!n.present) return 0.15
  if (focusId.value === null || n.id === focusId.value) return 1
  return drawn.value.some((e) => e.weight && ((e.a === focusId.value && e.b === n.id) || (e.b === focusId.value && e.a === n.id))) ? 1 : 0.25
}

function short(name) {
  return name.length > 20 ? name.slice(0, 19) + '…' : name
}

function pick(n) {
  if (!n.present) return
  selectedId.value = selectedId.value === n.id ? null : n.id
}

const selected = computed(() => (selectedId.value === null ? null : byId.value.get(selectedId.value) ?? null))

const connections = computed(() => {
  if (selectedId.value === null) return []
  return edges.value
    .filter((e) => e.a === selectedId.value || e.b === selectedId.value)
    .map((e) => ({ ...e, other: byId.value.get(e.a === selectedId.value ? e.b : e.a) }))
    .filter((e) => e.other)
    .sort((x, y) => y.weight - x.weight)
})

async function loadPhotos(list) {
  for (const c of list) {
    if (!c.has_photo || photos.value[c.id]) continue
    try {
      const { data: blob } = await api.get(`/documents/${props.id}/characters/${c.id}/photo`, { responseType: 'blob' })
      photos.value = { ...photos.value, [c.id]: URL.createObjectURL(blob) }
    } catch {
      /* tetap memakai inisial */
    }
  }
}

watch(characters, loadPhotos, { immediate: true })

const summaryLabel = computed(
  () => `Peta relasi: ${presentCount.value} tokoh dan ${edges.value.length} hubungan` + (atEnd.value ? ' di seluruh buku' : ` sampai bab ${chapterNumber.value}`),
)
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
        <p class="eyebrow">Relasi antar tokoh</p>
        <h1 class="text-3xl leading-tight font-semibold break-words sm:text-4xl">{{ doc.title }}</h1>
      </section>

      <p v-if="error" role="alert" class="flex items-start gap-2 rounded-lg bg-danger/10 px-3 py-2.5 text-sm text-danger">
        <Icon icon="lucide:circle-alert" class="mt-0.5 size-4 shrink-0" />
        {{ error }}
      </p>

      <NotNovelNotice v-if="doc.status === 'not_novel'" :id="id" />

      <TierLock
        v-else-if="locked"
        tier="middle"
        title="Fitur khusus Middle Tier"
        text="Deteksi tokoh dan relasi tersedia untuk pengguna Middle Tier ke atas. Hasil yang sudah pernah dibuat tetap bisa dilihat."
      />

      <section v-else-if="doc.status !== 'done'" class="card grid place-items-center gap-3 px-6 py-14 text-center">
        <Icon icon="lucide:hourglass" class="size-10 text-lavender" />
        <p class="max-w-md text-sm text-muted">Relasi tokoh bisa dilihat setelah analisis buku ini selesai.</p>
        <RouterLink :to="{ name: 'document', params: { id } }" class="btn btn-primary btn-sm">Lihat status analisis</RouterLink>
      </section>

      <section v-else-if="!data?.status" class="card grid place-items-center gap-4 px-6 py-14 text-center">
        <Icon icon="lucide:git-fork" class="size-12 text-navy" />
        <div class="space-y-1">
          <h2 class="text-2xl font-semibold">Deteksi tokoh dan relasinya</h2>
          <p class="max-w-md text-sm text-muted">Peta relasi disusun dari tokoh yang terdeteksi di buku ini. Prosesnya berjalan di server dan bisa memakan waktu beberapa menit.</p>
        </div>
        <button v-if="canCreate" class="btn btn-primary" :disabled="starting" @click="start()">
          <Icon :icon="starting ? 'lucide:loader-circle' : 'lucide:scan-search'" class="size-4.5" :class="{ 'animate-spin': starting }" />
          Deteksi tokoh
        </button>
      </section>

      <section v-else-if="data.status === 'running'" class="card grid place-items-center px-6 py-14">
        <ProgressLoader
          :percent="data.progress"
          title="Sedang mendeteksi tokoh"
          detail="Halaman ini memperbarui diri otomatis saat hasilnya siap."
          :tips="LOADING_TIPS.characters"
          icon="lucide:users"
        />
      </section>

      <section v-else-if="data.status === 'failed'" class="card grid place-items-center gap-4 px-6 py-14 text-center">
        <Icon icon="lucide:circle-x" class="size-12 text-danger" />
        <div class="space-y-1">
          <h2 class="text-2xl font-semibold">Tokoh gagal dideteksi</h2>
          <p class="max-w-md text-sm text-muted">Layanan AI belum bisa dihubungi atau gagal membaca buku ini. Coba lagi sebentar lagi.</p>
        </div>
        <button v-if="canCreate" class="btn btn-primary btn-sm" :disabled="starting" @click="start()">
          <Icon icon="lucide:refresh-cw" class="size-4" />
          Coba lagi
        </button>
      </section>

      <section v-else-if="characters.length < 2" class="card grid place-items-center gap-4 px-6 py-14 text-center">
        <Icon icon="lucide:users" class="size-12 text-lavender" />
        <div class="space-y-1">
          <h2 class="text-2xl font-semibold">Tokoh belum cukup</h2>
          <p class="max-w-md text-sm text-muted">Peta relasi membutuhkan minimal dua tokoh yang terdeteksi.</p>
        </div>
        <RouterLink :to="{ name: 'characters', params: { id } }" class="btn btn-quiet btn-sm">Lihat deskripsi tokoh</RouterLink>
      </section>

      <template v-else>
        <section class="card space-y-4 p-5 sm:p-6" aria-label="Pilih bab">
          <div class="flex flex-wrap items-end gap-3">
            <div class="min-w-0 flex-1 space-y-2">
              <div class="flex items-baseline justify-between gap-3">
                <label for="bab" class="text-sm font-semibold text-navy">Tinjau relasi sampai</label>
                <span class="truncate text-sm text-ink" aria-live="polite">{{ chapterLabel }}</span>
              </div>
              <input
                id="bab"
                type="range"
                min="0"
                :max="last"
                step="1"
                :value="current"
                :disabled="last === 0"
                aria-label="Bab"
                class="h-2 w-full cursor-pointer accent-navy"
                @input="slideTo(Number($event.target.value))"
              />
              <div class="flex justify-between text-[11px] text-muted" aria-hidden="true">
                <span>Bab {{ numbers[0] }}</span>
                <span>Bab {{ numbers[last] }}</span>
              </div>
            </div>
            <div class="flex gap-2">
              <button class="btn btn-outline" :disabled="current <= 0" aria-label="Bab sebelumnya" @click="slideTo(current - 1)">
                <Icon icon="lucide:chevron-left" class="size-4.5" />
              </button>
              <button class="btn btn-outline" :disabled="atEnd" aria-label="Bab berikutnya" @click="slideTo(current + 1)">
                <Icon icon="lucide:chevron-right" class="size-4.5" />
              </button>
              <button class="btn btn-primary" :disabled="last === 0" @click="togglePlay()">
                <Icon :icon="playing ? 'lucide:pause' : 'lucide:play'" class="size-4" />
                {{ playing ? 'Jeda' : 'Putar' }}
              </button>
            </div>
          </div>
          <div class="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted">
            <span v-for="[key, t] in legend" :key="key" class="inline-flex items-center gap-2">
              <svg width="28" height="8" aria-hidden="true">
                <line x1="0" y1="4" x2="28" y2="4" :stroke="t.color" stroke-width="3" :stroke-dasharray="t.dash" stroke-linecap="round" />
              </svg>
              {{ t.label }}
            </span>
            <span>Garis lebih tebal = lebih sering muncul bersama</span>
            <span>Tekan tokoh untuk melihat hubungannya</span>
          </div>
        </section>

        <div class="grid items-start gap-5 lg:gap-0 lg:transition-[grid-template-columns] lg:duration-500 lg:ease-out" :class="selected ? 'lg:grid-cols-[minmax(0,1fr)_21.25rem]' : 'lg:grid-cols-[minmax(0,1fr)_0rem]'">
          <section class="card p-3 sm:p-5">
            <p class="mb-2 text-center text-xs text-muted sm:hidden">Geser ke samping untuk melihat seluruh graf.</p>
            <p v-if="!edges.length" class="mb-2 text-center text-sm text-muted">Belum ada relasi terdeteksi sampai bab ini.</p>
            <div :ref="centerScroll" class="overflow-x-auto">
              <svg :viewBox="`0 0 ${W} ${H}`" role="img" :aria-label="summaryLabel" class="mx-auto h-auto w-full max-w-3xl min-w-[640px]">
                <g>
                  <line
                    v-for="e in drawn"
                    :key="e.key"
                    :x1="e.p.x"
                    :y1="e.p.y"
                    :x2="e.q.x"
                    :y2="e.q.y"
                    :stroke-width="e.width"
                    :stroke="relationType(e.type).color"
                    :stroke-dasharray="relationType(e.type).dash"
                    stroke-linecap="round"
                    :style="{ opacity: edgeOpacity(e), strokeWidth: e.width + 'px', stroke: relationType(e.type).color, transition: 'opacity 400ms ease, stroke-width 400ms ease, stroke 400ms ease' }"
                  >
                    <title>{{ e.p.name }} dan {{ e.q.name }}: {{ relationType(e.type).label }}, {{ e.weight }} kali muncul bersama</title>
                  </line>
                </g>
                <g
                  v-for="n in nodes"
                  :key="n.id"
                  :tabindex="n.present ? 0 : -1"
                  :aria-disabled="!n.present"
                  :class="n.present ? 'cursor-pointer' : 'pointer-events-none'"
                  class="outline-none"
                  :style="{ opacity: nodeOpacity(n), transition: 'opacity 400ms ease' }"
                  @mouseenter="hover = n.present ? n.id : null"
                  @mouseleave="hover = null"
                  @focus="hover = n.present ? n.id : null"
                  @blur="hover = null"
                  @click="pick(n)"
                  @keydown.enter.prevent="pick(n)"
                  @keydown.space.prevent="pick(n)"
                >
                  <clipPath :id="`foto-${n.id}`"><circle :cx="n.x" :cy="n.y" :r="n.r" /></clipPath>
                  <circle :cx="n.x" :cy="n.y" :r="n.r" :stroke-width="selectedId === n.id ? 4 : 2.5" :class="selectedId === n.id ? 'stroke-lavender' : 'stroke-white'" class="fill-navy" />
                  <image
                    v-if="photos[n.id]"
                    :href="photos[n.id]"
                    :x="n.x - n.r"
                    :y="n.y - n.r"
                    :width="n.r * 2"
                    :height="n.r * 2"
                    preserveAspectRatio="xMidYMid slice"
                    :clip-path="`url(#foto-${n.id})`"
                  />
                  <text v-else data-test="inisial" :x="n.x" :y="n.y + 4" text-anchor="middle" font-size="12" font-weight="600" class="fill-white">{{ initials(n.name) }}</text>
                  <text
                    :x="n.lx"
                    :y="n.ly"
                    :text-anchor="n.anchor"
                    font-size="13"
                    font-weight="600"
                    stroke="white"
                    stroke-width="4"
                    paint-order="stroke"
                    class="fill-navy"
                  >{{ short(n.name) }}</text>
                </g>
              </svg>
            </div>
          </section>

          <Transition enter-active-class="transition duration-500 ease-out" enter-from-class="translate-x-8 opacity-0" leave-active-class="transition duration-200 ease-in" leave-to-class="translate-x-8 opacity-0">
          <aside v-if="selected" data-test="detail" class="card min-w-0 space-y-4 p-5 lg:ml-5" aria-label="Detail tokoh">
            <div class="flex items-center gap-3">
              <span class="grid size-14 shrink-0 place-items-center overflow-hidden rounded-full bg-navy font-display text-lg font-semibold text-white">
                <img v-if="photos[selected.id]" :src="photos[selected.id]" :alt="`Foto ${selected.name}`" class="size-full object-cover" />
                <template v-else>{{ initials(selected.name) }}</template>
              </span>
              <h2 class="min-w-0 flex-1 text-xl leading-snug font-semibold break-words">{{ selected.name }}</h2>
              <button class="btn btn-quiet btn-sm" @click="selectedId = null">Tutup</button>
            </div>
            <p v-if="selected.aliases" class="text-xs text-muted">Juga disebut: {{ selected.aliases }}</p>
            <p v-if="selected.biodata" class="text-sm leading-relaxed text-navy/90">{{ selected.biodata }}</p>
            <div class="space-y-2">
              <h3 class="text-sm font-semibold text-navy">Terhubung dengan</h3>
              <p v-if="!connections.length" class="text-sm text-muted">Belum terhubung dengan tokoh lain sampai bab ini.</p>
              <ul v-else class="divide-y divide-line">
                <li v-for="c in connections" :key="c.key" class="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                  <button data-test="ke-tokoh" class="min-w-0 text-left font-semibold text-navy underline-offset-2 hover:underline" @click="selectedId = c.other.id">{{ c.other.name }}</button>
                  <span class="flex items-center gap-2">
                    <span class="text-xs text-muted">{{ c.weight }} kali bersama</span>
                    <span class="chip" :style="{ background: relationType(c.type).color + '22', color: relationType(c.type).color }">{{ relationType(c.type).label }}</span>
                  </span>
                </li>
              </ul>
            </div>
          </aside>
          </Transition>
        </div>

        <section v-if="edges.length" class="space-y-3" aria-labelledby="daftar-relasi">
          <h2 id="daftar-relasi" class="text-xl font-semibold">Hubungan terdeteksi</h2>
          <ul data-test="daftar-hubungan" class="card max-h-96 divide-y divide-line overflow-y-auto">
            <li v-for="e in listed" :key="e.key" class="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
              <span class="min-w-0 font-semibold text-navy">{{ byId.get(e.a)?.name }} <span class="font-normal text-muted">dan</span> {{ byId.get(e.b)?.name }}</span>
              <span class="flex items-center gap-3">
                <span class="text-xs text-muted">{{ e.weight }} kali bersama</span>
                <span class="chip" :style="{ background: relationType(e.type).color + '22', color: relationType(e.type).color }">{{ relationType(e.type).label }}</span>
              </span>
            </li>
          </ul>
        </section>

        <div class="flex flex-wrap items-center justify-between gap-3">
          <p class="flex items-start gap-2 text-xs text-muted sm:max-w-2xl">
            <Icon icon="lucide:info" class="mt-0.5 size-3.5 shrink-0" />
            Hubungan dibaca AI dari isi cerita dan hanya ditampilkan bila ada kutipan yang mendukungnya, tetapi jenis hubungan tetap perkiraan sehingga bisa keliru.
          </p>
          <RouterLink :to="{ name: 'characters', params: { id } }" class="btn btn-quiet btn-sm">
            <Icon icon="lucide:contact-round" class="size-4" />
            Deskripsi tokoh
          </RouterLink>
        </div>
      </template>
    </template>
  </div>
</template>
