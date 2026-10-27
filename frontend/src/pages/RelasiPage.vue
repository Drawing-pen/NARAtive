<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '@/lib/api'
import { hasTier } from '@/lib/auth'
import TierLock from '@/components/TierLock.vue'
import { RELATION_TYPES, ROLES, relationType } from '@/lib/content'
import { useCharacters } from '@/lib/characters'

const props = defineProps({ id: { type: String, required: true } })

const { doc, data, loading, missing, error, locked, starting, start } = useCharacters(() => props.id)
const canCreate = computed(() => hasTier('middle'))

const chapters = ref([])
const selected = ref(0)
const active = ref(null)

onMounted(async () => {
  try {
    chapters.value = (await api.get(`/documents/${props.id}/chapters`)).data
  } catch {
    chapters.value = []
  }
})

const W = 760
const H = 560
const CX = W / 2
const CY = H / 2
const RING = 190

const characters = computed(() => data.value?.characters ?? [])
const byId = computed(() => new Map(characters.value.map((c) => [c.id, c])))
const maxMentions = computed(() => Math.max(1, ...characters.value.map((c) => c.mention_count)))

const perChapter = computed(() => {
  const counts = new Map()
  for (const r of data.value?.relations ?? []) counts.set(r.chapter, (counts.get(r.chapter) ?? 0) + 1)
  return counts
})

const options = computed(() => [
  { value: 0, label: 'Semua bab' },
  ...chapters.value.map((c) => ({
    value: c.number,
    label: `Bab ${c.number} · ${c.title.length > 42 ? c.title.slice(0, 42) + '…' : c.title} (${perChapter.value.get(c.number) ?? 0} relasi)`,
  })),
])

const position = computed(() => options.value.findIndex((o) => o.value === selected.value))

function step(delta) {
  const next = options.value[position.value + delta]
  if (next) selected.value = next.value
}

const edges = computed(() => {
  const all = data.value?.relations ?? []
  if (selected.value) {
    return all
      .filter((r) => r.chapter === selected.value)
      .map((r) => ({ key: `${r.a}-${r.b}`, a: r.a, b: r.b, type: r.type, weight: r.weight }))
  }
  const merged = new Map()
  for (const r of all) {
    const key = `${r.a}-${r.b}`
    const cur = merged.get(key) ?? { key, a: r.a, b: r.b, weight: 0, kinds: new Map() }
    cur.weight += r.weight
    const kind = relationType(r.type).key
    cur.kinds.set(kind, (cur.kinds.get(kind) ?? 0) + r.weight)
    merged.set(key, cur)
  }
  return [...merged.values()].map(({ kinds, ...e }) => {
    const known = [...kinds].filter(([k]) => k !== 'kenalan')
    const pool = known.length ? known : [...kinds]
    return { ...e, type: pool.sort((x, y) => y[1] - x[1])[0][0] }
  })
})

const legend = computed(() => {
  const present = new Set(edges.value.map((e) => relationType(e.type).key))
  return Object.entries(RELATION_TYPES).filter(([key]) => present.has(key))
})

const maxWeight = computed(() => Math.max(1, ...edges.value.map((e) => e.weight)))

const nodes = computed(() => {
  const degree = new Map()
  for (const e of edges.value) {
    degree.set(e.a, (degree.get(e.a) ?? 0) + e.weight)
    degree.set(e.b, (degree.get(e.b) ?? 0) + e.weight)
  }
  const ids = [...degree.keys()].filter((id) => byId.value.has(id)).sort((x, y) => degree.get(y) - degree.get(x))
  return ids.map((id, i) => {
    const c = byId.value.get(id)
    const angle = -Math.PI / 2 + (2 * Math.PI * i) / ids.length
    const r = 9 + 13 * (c.mention_count / maxMentions.value)
    const x = CX + RING * Math.cos(angle)
    const y = CY + RING * Math.sin(angle)
    const cos = Math.cos(angle)
    return {
      id,
      name: c.name,
      role: c.role,
      x,
      y,
      r,
      lx: x + (r + 8) * cos,
      ly: y + (r + 8) * Math.sin(angle) + 4,
      anchor: cos > 0.15 ? 'start' : cos < -0.15 ? 'end' : 'middle',
    }
  })
})

const nodeById = computed(() => new Map(nodes.value.map((n) => [n.id, n])))

const drawn = computed(() =>
  edges.value
    .filter((e) => nodeById.value.has(e.a) && nodeById.value.has(e.b))
    .map((e) => ({ ...e, p: nodeById.value.get(e.a), q: nodeById.value.get(e.b), width: 1.5 + (6 * e.weight) / maxWeight.value })),
)

const listed = computed(() => [...edges.value].sort((x, y) => y.weight - x.weight))

function edgeOpacity(e) {
  if (active.value === null) return 0.7
  return e.a === active.value || e.b === active.value ? 1 : 0.08
}

function nodeOpacity(n) {
  if (active.value === null || n.id === active.value) return 1
  return drawn.value.some((e) => (e.a === active.value && e.b === n.id) || (e.b === active.value && e.a === n.id)) ? 1 : 0.25
}

function short(name) {
  return name.length > 20 ? name.slice(0, 19) + '…' : name
}

const summaryLabel = computed(
  () => `Peta relasi: ${nodes.value.length} tokoh dan ${drawn.value.length} hubungan` + (selected.value ? ` pada bab ${selected.value}` : ' di seluruh buku'),
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

      <TierLock
        v-if="locked"
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

      <section v-else-if="characters.length < 2" class="card grid place-items-center gap-4 px-6 py-14 text-center">
        <Icon icon="lucide:users" class="size-12 text-lavender" />
        <div class="space-y-1">
          <h2 class="text-2xl font-semibold">Tokoh belum cukup</h2>
          <p class="max-w-md text-sm text-muted">Peta relasi membutuhkan minimal dua tokoh yang terdeteksi.</p>
        </div>
        <RouterLink :to="{ name: 'characters', params: { id } }" class="btn btn-quiet btn-sm">Lihat biodata tokoh</RouterLink>
      </section>

      <template v-else>
        <section class="card space-y-4 p-5 sm:p-6" aria-label="Pilih bab">
          <div class="flex flex-wrap items-end gap-3">
            <div class="min-w-0 flex-1 space-y-1.5">
              <label for="bab" class="text-sm font-semibold text-navy">Tinjau relasi pada</label>
              <select
                id="bab"
                v-model.number="selected"
                class="w-full rounded-lg border border-line bg-paper px-3 py-2.5 text-[15px] text-ink focus:border-lavender focus:bg-white focus:ring-2 focus:ring-lavender/30 focus:outline-none"
              >
                <option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option>
              </select>
            </div>
            <div class="flex gap-2">
              <button class="btn btn-outline" :disabled="position <= 0" aria-label="Bab sebelumnya" @click="step(-1)">
                <Icon icon="lucide:chevron-left" class="size-4.5" />
              </button>
              <button class="btn btn-outline" :disabled="position >= options.length - 1" aria-label="Bab berikutnya" @click="step(1)">
                <Icon icon="lucide:chevron-right" class="size-4.5" />
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
                      </div>
        </section>

        <section v-if="!drawn.length" class="card grid place-items-center gap-3 px-6 py-14 text-center">
          <Icon icon="lucide:unlink" class="size-10 text-lavender" />
          <p class="text-sm text-muted">Belum ada relasi terdeteksi pada bab ini.</p>
        </section>

        <template v-else>
          <section class="card p-3 sm:p-5">
            <svg :viewBox="`0 0 ${W} ${H}`" role="img" :aria-label="summaryLabel" class="mx-auto h-auto w-full max-w-3xl">
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
                  class="transition-opacity"
                  :style="{ opacity: edgeOpacity(e) }"
                >
                  <title>{{ e.p.name }} dan {{ e.q.name }}: {{ relationType(e.type).label }}, {{ e.weight }} kali muncul bersama</title>
                </line>
              </g>
              <g
                v-for="n in nodes"
                :key="n.id"
                tabindex="0"
                class="cursor-pointer outline-none transition-opacity"
                :style="{ opacity: nodeOpacity(n) }"
                @mouseenter="active = n.id"
                @mouseleave="active = null"
                @focus="active = n.id"
                @blur="active = null"
              >
                <circle :cx="n.x" :cy="n.y" :r="n.r" stroke-width="2.5" class="stroke-white" :class="ROLES[n.role]?.node" />
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
          </section>

          <section class="space-y-3" aria-labelledby="daftar-relasi">
            <h2 id="daftar-relasi" class="text-xl font-semibold">Hubungan terdeteksi</h2>
            <ul class="card max-h-96 divide-y divide-line overflow-y-auto">
              <li v-for="e in listed" :key="e.key" class="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm">
                <span class="min-w-0 font-semibold text-navy">{{ byId.get(e.a)?.name }} <span class="font-normal text-muted">dan</span> {{ byId.get(e.b)?.name }}</span>
                <span class="flex items-center gap-3">
                  <span class="text-xs text-muted">{{ e.weight }} kali bersama</span>
                  <span class="chip" :style="{ background: relationType(e.type).color + '22', color: relationType(e.type).color }">{{ relationType(e.type).label }}</span>
                </span>
              </li>
            </ul>
          </section>
        </template>

        <div class="flex flex-wrap items-center justify-between gap-3">
          <p class="flex items-start gap-2 text-xs text-muted sm:max-w-2xl">
            <Icon icon="lucide:info" class="mt-0.5 size-3.5 shrink-0" />
            Jenis hubungan diperkirakan dari kata-kata di paragraf tempat dua tokoh muncul bersama (misalnya “kekasih”, “sahabat”, “membenci”) dan nada paragrafnya, sehingga bisa keliru. Pasangan yang tidak punya petunjuk jelas ditandai Kenalan.
          </p>
          <RouterLink :to="{ name: 'characters', params: { id } }" class="btn btn-quiet btn-sm">
            <Icon icon="lucide:contact-round" class="size-4" />
            Biodata tokoh
          </RouterLink>
        </div>
      </template>
    </template>
  </div>
</template>