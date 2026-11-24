import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'

const allowed = { middle: true }
const start = vi.fn()
let state

vi.mock('@/lib/auth', () => ({ hasTier: () => allowed.middle }))
vi.mock('@/lib/characters', () => ({ useCharacters: () => state }))

import TokohPage from '@/pages/TokohPage.vue'

const DOC = { id: 1, title: 'Buku Uji', status: 'done' }

function setup(overrides = {}) {
  state = {
    doc: ref(DOC),
    data: ref({ status: 'done', characters: [] }),
    loading: ref(false),
    missing: ref(false),
    error: ref(''),
    locked: ref(false),
    starting: ref(false),
    start,
    ...overrides,
  }
}

function open() {
  return mount(TokohPage, {
    props: { id: '1' },
    global: {
      stubs: {
        Icon: true,
        RouterLink: { template: '<a><slot /></a>' },
        AuthImage: { template: '<span><slot /></span>' },
        PictureControls: true,
        TierLock: { template: '<div data-test="lock" />' },
      },
    },
  })
}

const buttonByText = (w, text) => w.findAll('button').find((b) => b.text().includes(text))

const CHARACTERS = [
  { id: 1, name: 'Rana Dzikro', aliases: 'Ra', biodata: 'Mahasiswa yang suka membaca.', has_photo: false },
  { id: 2, name: 'Dede', aliases: '', biodata: 'Sahabat Rana.', has_photo: false },
]

beforeEach(() => {
  start.mockReset()
  allowed.middle = true
  setup()
})

describe('TokohPage', () => {
  it('menampilkan keadaan memuat', () => {
    setup({ loading: ref(true), doc: ref(null) })
    expect(open().text()).toContain('Memuat')
  })

  it('menampilkan dokumen tidak ditemukan', () => {
    setup({ missing: ref(true), doc: ref(null) })
    expect(open().text()).toContain('Dokumen tidak ditemukan')
  })

  it('menampilkan pesan galat', () => {
    setup({ error: ref('Gagal memuat.') })
    expect(open().find('[role="alert"]').text()).toContain('Gagal memuat.')
  })

  it('menampilkan kunci tier bagi pengguna yang tidak berhak dan belum punya hasil', () => {
    setup({ locked: ref(true) })
    expect(open().find('[data-test="lock"]').exists()).toBe(true)
  })

  it('meminta menunggu analisis bila buku belum selesai dianalisis', () => {
    setup({ doc: ref({ ...DOC, status: 'analyzing' }) })
    expect(open().text()).toContain('setelah analisis buku ini selesai')
  })

  it('menawarkan deteksi tokoh bila belum pernah dibuat dan memulainya saat diklik', async () => {
    setup({ data: ref({ status: null, characters: [] }) })
    const w = open()
    await buttonByText(w, 'Deteksi tokoh').trigger('click')
    expect(start).toHaveBeenCalledTimes(1)
  })

  it('menyembunyikan tombol deteksi bagi yang tidak berhak', () => {
    allowed.middle = false
    setup({ data: ref({ status: null, characters: [] }) })
    expect(buttonByText(open(), 'Deteksi tokoh')).toBeUndefined()
  })

  it('menampilkan kemajuan saat sedang mendeteksi', () => {
    setup({ data: ref({ status: 'running', progress: 35, characters: [] }) })
    const w = open()
    expect(w.text()).toContain('Sedang mendeteksi tokoh')
    expect(w.find('[data-test="percent"]').text()).toBe('35%')
    expect(w.find('[role="progressbar"]').attributes('aria-valuenow')).toBe('35')
  })

  it('dokumen bukan novel terkunci dengan pesan khusus', () => {
    setup({ doc: ref({ ...DOC, status: 'not_novel' }), data: ref({ status: null, characters: [] }) })
    const w = open()
    expect(w.text()).toContain('Dokumen ini bukan novel')
    expect(w.text()).not.toContain('setelah analisis buku ini selesai')
    expect(buttonByText(w, 'Deteksi tokoh')).toBeUndefined()
  })

  it('pesan bukan novel lebih diutamakan daripada kunci tingkatan', () => {
    allowed.middle = false
    setup({ doc: ref({ ...DOC, status: 'not_novel' }), data: ref({ status: null, characters: [] }), locked: ref(true) })
    expect(open().text()).toContain('Dokumen ini bukan novel')
    allowed.middle = true
  })

  it('tanpa angka dari server tampil sebagai keadaan tak tentu', () => {
    setup({ data: ref({ status: 'running', progress: null, characters: [] }) })
    expect(open().find('[data-test="fill"]').classes()).toContain('is-indeterminate')
  })

  it('menawarkan coba lagi saat deteksi gagal', async () => {
    setup({ data: ref({ status: 'failed', characters: [] }) })
    const w = open()
    expect(w.text()).toContain('Tokoh gagal dideteksi')
    await buttonByText(w, 'Coba lagi').trigger('click')
    expect(start).toHaveBeenCalled()
  })

  it('menampilkan keadaan kosong saat tidak ada tokoh', () => {
    expect(open().text()).toContain('Tokoh tidak terdeteksi')
  })

  it('menampilkan kartu tokoh hanya dengan nama, nama lain, dan deskripsi', () => {
    setup({ data: ref({ status: 'done', characters: CHARACTERS }) })
    const w = open()
    const cards = w.findAll('article')
    expect(cards).toHaveLength(2)
    expect(cards[0].text()).toContain('Rana Dzikro')
    expect(cards[0].text()).toContain('Juga disebut: Ra')
    expect(cards[0].text()).toContain('Mahasiswa yang suka membaca.')
    expect(cards[1].text()).not.toContain('Juga disebut')
    expect(w.text()).toContain('2 tokoh terdeteksi')
  })

  it('status partial tampil seperti biasa tanpa pemberitahuan', () => {
    setup({ data: ref({ status: 'partial', characters: CHARACTERS }) })
    const w = open()
    expect(w.findAll('article')).toHaveLength(2)
    expect(w.text()).not.toMatch(/sebagian|partial/i)
  })

  it('Deteksi ulang memulai ulang proses', async () => {
    setup({ data: ref({ status: 'done', characters: CHARACTERS }) })
    const w = open()
    await buttonByText(w, 'Deteksi ulang').trigger('click')
    expect(start).toHaveBeenCalled()
  })
})
