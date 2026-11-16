import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'

const allowed = { middle: true }
const start = vi.fn()
const get = vi.fn()
let state

vi.mock('@/lib/api', () => ({ default: { get: (...args) => get(...args) } }))
vi.mock('@/lib/auth', () => ({ hasTier: () => allowed.middle }))
vi.mock('@/lib/characters', () => ({ useCharacters: () => state }))

import RelasiPage from '@/pages/RelasiPage.vue'

const DOC = { id: 1, title: 'Buku Uji', status: 'done' }
const CHAPTERS = [
  { number: 1, title: 'Awal' },
  { number: 2, title: 'Bab dengan judul yang sangat panjang sekali sampai dipotong' },
]
const PEOPLE = [
  { id: 1, name: 'Rana', mention_count: 30, aliases: 'Ran', biodata: 'Tokoh utama cerita.', has_photo: false },
  { id: 2, name: 'Dede', mention_count: 20 },
  { id: 3, name: 'Budi', mention_count: 5 },
]
const RELATIONS = [
  { a: 1, b: 2, type: 'sahabat', weight: 4, chapter: 1 },
  { a: 1, b: 2, type: 'kenalan', weight: 1, chapter: 2 },
  { a: 2, b: 3, type: 'musuh', weight: 2, chapter: 2 },
]

function setup(overrides = {}) {
  state = {
    doc: ref(DOC),
    data: ref({ status: 'done', characters: PEOPLE, relations: RELATIONS }),
    loading: ref(false),
    missing: ref(false),
    error: ref(''),
    locked: ref(false),
    starting: ref(false),
    start,
    ...overrides,
  }
}

async function open() {
  const wrapper = mount(RelasiPage, {
    props: { id: '1' },
    global: { stubs: { Icon: true, RouterLink: { template: '<a><slot /></a>' }, TierLock: { template: '<div data-test="lock" />' } } },
  })
  await flushPromises()
  return wrapper
}

const buttonByText = (w, text) => w.findAll('button').find((b) => b.text().includes(text))

beforeEach(() => {
  start.mockReset()
  get.mockReset()
  get.mockImplementation(async (path) => (path.endsWith('/chapters') ? { data: CHAPTERS } : { data: new Blob(['x']) }))
  URL.createObjectURL = vi.fn(() => 'blob:foto')
  URL.revokeObjectURL = vi.fn()
  allowed.middle = true
  setup()
})

describe('RelasiPage keadaan', () => {
  it('memuat', async () => {
    setup({ loading: ref(true), doc: ref(null) })
    expect((await open()).text()).toContain('Memuat')
  })

  it('dokumen tidak ditemukan', async () => {
    setup({ missing: ref(true), doc: ref(null) })
    expect((await open()).text()).toContain('Dokumen tidak ditemukan')
  })

  it('kunci tier', async () => {
    setup({ locked: ref(true) })
    expect((await open()).find('[data-test="lock"]').exists()).toBe(true)
  })

  it('buku belum selesai dianalisis', async () => {
    setup({ doc: ref({ ...DOC, status: 'queued' }) })
    expect((await open()).text()).toContain('setelah analisis buku ini selesai')
  })

  it('belum pernah dideteksi menawarkan tombol deteksi', async () => {
    setup({ data: ref({ status: null, characters: [], relations: [] }) })
    const w = await open()
    await buttonByText(w, 'Deteksi tokoh').trigger('click')
    expect(start).toHaveBeenCalledTimes(1)
  })

  it('sedang berjalan', async () => {
    setup({ data: ref({ status: 'running', characters: [], relations: [] }) })
    expect((await open()).text()).toContain('Sedang mendeteksi tokoh')
  })

  it('gagal menawarkan coba lagi', async () => {
    setup({ data: ref({ status: 'failed', characters: [], relations: [] }) })
    const w = await open()
    await buttonByText(w, 'Coba lagi').trigger('click')
    expect(start).toHaveBeenCalled()
  })

  it('kurang dari dua tokoh', async () => {
    setup({ data: ref({ status: 'done', characters: [PEOPLE[0]], relations: [] }) })
    expect((await open()).text()).toContain('Tokoh belum cukup')
  })
})

describe('RelasiPage peta', () => {
  const slider = (w) => w.find('input[type="range"]')
  const nodeOf = (w, name) => w.findAll('svg g[tabindex]').find((g) => g.text().includes(name))

  it('menggambar simpul dan garis seluruh buku dengan jenis dominan', async () => {
    const w = await open()
    expect(w.findAll('svg g[tabindex="0"]')).toHaveLength(3)
    expect(w.findAll('svg line[stroke-width]').length).toBeGreaterThanOrEqual(2)
    expect(w.find('svg[role="img"]').attributes('aria-label')).toBe('Peta relasi: 3 tokoh dan 2 hubungan di seluruh buku')
  })

  it('pilihan bab berupa slider, bukan dropdown, dan awalnya di bab terakhir', async () => {
    const w = await open()
    expect(w.find('select').exists()).toBe(false)
    expect(slider(w).attributes('max')).toBe('1')
    expect(slider(w).element.value).toBe('1')
    expect(w.text()).toContain('Bab 2')
    expect(w.text()).toContain('…')
  })

  it('pasangan yang sama digabung dan jenis bukan kenalan menang', async () => {
    const w = await open()
    const rows = w.findAll('[data-test="daftar-hubungan"] li')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('Rana')
    expect(rows[0].text()).toContain('5 kali bersama')
    expect(rows[0].text()).toContain('Sahabat')
    expect(rows[1].text()).toContain('2 kali bersama')
  })

  it('menggeser slider ke bab awal menampilkan relasi kumulatif sampai bab itu', async () => {
    const w = await open()
    await slider(w).setValue('0')
    const rows = w.findAll('[data-test="daftar-hubungan"] li')
    expect(rows).toHaveLength(1)
    expect(rows[0].text()).toContain('4 kali bersama')
    expect(w.find('svg[role="img"]').attributes('aria-label')).toContain('sampai bab 1')
    expect(w.text()).toContain('Bab 1')
  })

  it('posisi simpul tetap dan tokoh yang belum punya relasi tersamar dan tidak bisa difokus', async () => {
    const w = await open()
    const before = nodeOf(w, 'Budi').find('circle').attributes('cx')
    await slider(w).setValue('0')
    expect(nodeOf(w, 'Budi').find('circle').attributes('cx')).toBe(before)
    expect(nodeOf(w, 'Budi').attributes('tabindex')).toBe('-1')
    expect(w.findAll('svg g[tabindex="0"]')).toHaveLength(2)
  })

  it('bab tanpa relasi sampai titik itu menampilkan keadaan kosong tetapi slider tetap ada', async () => {
    setup({ data: ref({ status: 'done', characters: PEOPLE, relations: [{ a: 1, b: 2, type: 'sahabat', weight: 3, chapter: 2 }] }) })
    const w = await open()
    await slider(w).setValue('0')
    expect(w.text()).toContain('Belum ada relasi terdeteksi sampai bab ini.')
    expect(slider(w).exists()).toBe(true)
  })

  it('tombol bab berikutnya dan sebelumnya menggeser slider dan dibatasi di ujung', async () => {
    const w = await open()
    const prev = w.find('[aria-label="Bab sebelumnya"]')
    const next = w.find('[aria-label="Bab berikutnya"]')
    expect(next.attributes('disabled')).toBeDefined()
    await prev.trigger('click')
    expect(slider(w).element.value).toBe('0')
    expect(prev.attributes('disabled')).toBeDefined()
    await next.trigger('click')
    expect(slider(w).element.value).toBe('1')
  })

  describe('putar otomatis', () => {
    beforeEach(() => vi.useFakeTimers())
    afterEach(() => vi.useRealTimers())

    it('maju satu bab tiap 1,2 detik lalu berhenti di bab terakhir', async () => {
      const w = await open()
      await slider(w).setValue('0')
      await buttonByText(w, 'Putar').trigger('click')
      expect(buttonByText(w, 'Jeda')).toBeTruthy()
      await vi.advanceTimersByTimeAsync(1200)
      expect(slider(w).element.value).toBe('1')
      await vi.advanceTimersByTimeAsync(1200)
      expect(buttonByText(w, 'Putar')).toBeTruthy()
    })

    it('Putar di bab terakhir mengulang dari bab pertama dan Jeda menghentikan', async () => {
      const w = await open()
      await buttonByText(w, 'Putar').trigger('click')
      expect(slider(w).element.value).toBe('0')
      await buttonByText(w, 'Jeda').trigger('click')
      await vi.advanceTimersByTimeAsync(3000)
      expect(slider(w).element.value).toBe('0')
    })

    it('menggeser slider sendiri menghentikan putaran', async () => {
      const w = await open()
      await slider(w).setValue('0')
      await buttonByText(w, 'Putar').trigger('click')
      await slider(w).setValue('0')
      expect(buttonByText(w, 'Putar')).toBeTruthy()
    })
  })

  it('legenda hanya memuat jenis yang tampil', async () => {
    const w = await open()
    const text = w.text()
    expect(text).toContain('Sahabat')
    expect(text).toContain('Musuh')
    expect(text).not.toContain('Pasangan')
  })

  it('gagal memuat daftar bab: slider memakai nomor bab dari relasi', async () => {
    get.mockRejectedValue(new Error('mati'))
    const w = await open()
    expect(slider(w).attributes('max')).toBe('1')
    expect(w.findAll('[data-test="daftar-hubungan"] li').length).toBeGreaterThan(0)
  })
})

describe('RelasiPage detail tokoh', () => {
  const nodeOf = (w, name) => w.findAll('svg g[tabindex]').find((g) => g.text().includes(name))

  it('menekan simpul membuka panel dengan biodata dan tokoh yang terhubung', async () => {
    const w = await open()
    expect(w.find('[data-test="detail"]').exists()).toBe(false)
    await nodeOf(w, 'Rana').trigger('click')
    const panel = w.find('[data-test="detail"]')
    expect(panel.text()).toContain('Rana')
    expect(panel.text()).toContain('Juga disebut: Ran')
    expect(panel.text()).toContain('Tokoh utama cerita.')
    expect(panel.text()).toContain('Dede')
    expect(panel.text()).toContain('5 kali bersama')
    expect(panel.text()).toContain('Sahabat')
    expect(panel.text()).not.toContain('Budi')
  })

  it('daftar terhubung mengikuti bab pada slider', async () => {
    const w = await open()
    await nodeOf(w, 'Dede').trigger('click')
    expect(w.find('[data-test="detail"]').text()).toContain('Budi')
    await w.find('input[type="range"]').setValue('0')
    expect(w.find('[data-test="detail"]').text()).not.toContain('Budi')
  })

  it('menekan nama tokoh terhubung berpindah ke tokoh itu', async () => {
    const w = await open()
    await nodeOf(w, 'Rana').trigger('click')
    await w.find('[data-test="detail"] button[data-test="ke-tokoh"]').trigger('click')
    expect(w.find('[data-test="detail"] h2').text()).toBe('Dede')
  })

  it('Enter pada simpul membuka detail dan menekan simpul sama atau Tutup menutupnya', async () => {
    const w = await open()
    await nodeOf(w, 'Rana').trigger('keydown.enter')
    expect(w.find('[data-test="detail"]').exists()).toBe(true)
    await nodeOf(w, 'Rana').trigger('click')
    expect(w.find('[data-test="detail"]').exists()).toBe(false)
    await nodeOf(w, 'Rana').trigger('click')
    await buttonByText(w, 'Tutup').trigger('click')
    expect(w.find('[data-test="detail"]').exists()).toBe(false)
  })

  it('tokoh terpilih menyorot garisnya dan meredupkan yang lain', async () => {
    const w = await open()
    await nodeOf(w, 'Rana').trigger('click')
    const lines = w.findAll('svg[role="img"] line')
    const dim = lines.filter((l) => l.attributes('style').includes('0.08'))
    expect(dim).toHaveLength(1)
  })
})

describe('RelasiPage foto tokoh', () => {
  const withPhoto = () =>
    setup({ data: ref({ status: 'done', characters: [{ ...PEOPLE[0], has_photo: true }, PEOPLE[1], PEOPLE[2]], relations: RELATIONS }) })

  it('memuat foto tokoh yang punya foto dan memakainya di simpul', async () => {
    withPhoto()
    const w = await open()
    expect(get).toHaveBeenCalledWith('/documents/1/characters/1/photo', { responseType: 'blob' })
    expect(get).not.toHaveBeenCalledWith('/documents/1/characters/2/photo', expect.anything())
    expect(w.findAll('svg image')).toHaveLength(1)
    expect(w.find('svg image').attributes('href')).toBe('blob:foto')
  })

  it('gagal memuat foto: simpul memakai inisial', async () => {
    withPhoto()
    get.mockImplementation(async (path) => {
      if (path.endsWith('/chapters')) return { data: CHAPTERS }
      throw new Error('404')
    })
    const w = await open()
    expect(w.findAll('svg image')).toHaveLength(0)
    expect(w.findAll('svg g[tabindex]').find((g) => g.text().includes('Rana')).find('[data-test="inisial"]').text()).toBe('R')
  })

  it('panel detail juga menampilkan foto', async () => {
    withPhoto()
    const w = await open()
    await w.findAll('svg g[tabindex]').find((g) => g.text().includes('Rana')).trigger('click')
    expect(w.find('[data-test="detail"] img').attributes('src')).toBe('blob:foto')
  })
})
