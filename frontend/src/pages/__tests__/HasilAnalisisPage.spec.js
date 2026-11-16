import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const get = vi.fn()
const tier = vi.hoisted(() => ({ allowed: true }))

vi.mock('@/lib/api', () => ({
  default: { get: (...args) => get(...args), patch: vi.fn() },
  errorMessage: (e, fallback) => e?.response?.data?.detail ?? fallback,
}))
vi.mock('@/lib/auth', () => ({ hasTier: () => tier.allowed }))

import HasilAnalisisPage from '@/pages/HasilAnalisisPage.vue'
import { closeUpgrade, upgrade } from '@/lib/upgrade'

const DOC = (o = {}) => ({
  id: 7, title: 'Buku Uji', status: 'reading', rating: null, page_count: 300, read_pages: 120, failure_reason: null,
  created_at: '2026-11-01T08:00:00', has_cover: false, estimated_seconds: null, ...o,
})

const BREAKDOWN = {
  rating: 'Teen', age_range: '13+',
  dimensions: [
    { key: 'violence', label: 'Kekerasan', percent: 4.2, paragraphs: 9, threshold: 0.8 },
    { key: 'sexual', label: 'Konten seksual', percent: 0.4, paragraphs: 1, threshold: 0.5 },
    { key: 'profanity', label: 'Bahasa kasar', percent: 12.5, paragraphs: 27, threshold: 0.5 },
  ],
  reasons: ['Kekerasan 4,2% paragraf (9 paragraf) mencapai batas Teen: minimal 3% dan 2 paragraf.'],
  note: 'Bahasa kasar ditampilkan sebagai informasi dan tidak dihitung dalam rating maupun persentase konten dewasa.',
}
let ratingResponse = () => Promise.resolve({ data: BREAKDOWN })

async function open(doc) {
  get.mockImplementation((url) => (url.endsWith('/rating') ? ratingResponse() : Promise.resolve({ data: doc })))
  const wrapper = mount(HasilAnalisisPage, {
    props: { id: '7' },
    global: {
      stubs: {
        Icon: true,
        RouterLink: { template: '<a><slot /></a>' },
        AuthImage: { template: '<div><slot /></div>' },
        PictureControls: true,
        RatingBadge: true,
        SoonButton: true,
        TierChip: true,
      },
    },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.useFakeTimers()
  get.mockReset()
  tier.allowed = true
  ratingResponse = () => Promise.resolve({ data: BREAKDOWN })
})
afterEach(() => vi.useRealTimers())

describe('halaman hasil saat berkas sedang dibaca', () => {
  it('menampilkan progres halaman', async () => {
    const w = await open(DOC())
    expect(w.text()).toContain('Membaca berkas')
    expect(w.text()).toContain('Membaca halaman 120 dari 300')
    expect(w.find('[role="progressbar"]').attributes('aria-valuenow')).toBe('120')
  })

  it('tidak menyebut OCR, scan, atau gambar', async () => {
    const text = (await open(DOC())).text().toLowerCase()
    for (const word of ['ocr', 'scan', 'gambar']) expect(text).not.toContain(word)
  })

  it('memperbarui diri selama masih dibaca', async () => {
    await open(DOC())
    get.mockClear()
    get.mockResolvedValue({ data: DOC({ read_pages: 200 }) })
    await vi.advanceTimersByTimeAsync(3100)
    expect(get).toHaveBeenCalledWith('/documents/7')
  })

  it('berhenti memperbarui setelah selesai', async () => {
    await open(DOC({ status: 'done', rating: 'Teen', pct_adult: 2, heaviness: 10 }))
    get.mockClear()
    await vi.advanceTimersByTimeAsync(7000)
    expect(get).not.toHaveBeenCalled()
  })
})

describe('halaman hasil saat gagal', () => {
  it('menampilkan alasan dari server', async () => {
    const w = await open(DOC({ status: 'failed', failure_reason: 'Teks pada berkas ini tidak terbaca dengan baik. Coba berkas dengan kualitas lebih tinggi.' }))
    expect(w.text()).toContain('Teks pada berkas ini tidak terbaca dengan baik.')
  })

  it('memakai teks lama bila tidak ada alasan', async () => {
    const w = await open(DOC({ status: 'failed' }))
    expect(w.text()).toContain('Sistem tidak berhasil memproses naskah ini.')
  })
})

describe('halaman hasil saat menunggu analisis', () => {
  it('tetap menampilkan perkiraan waktu', async () => {
    const w = await open(DOC({ status: 'queued', estimated_seconds: 60 }))
    expect(w.text()).toContain('Menunggu giliran')
    expect(w.text()).toContain('sekitar 60 detik')
  })
})

const DONE = (o = {}) => DOC({ status: 'done', rating: 'Teen', pct_adult: 4.6, heaviness: 12, read_pages: 300, ...o })
const ratingCalls = () => get.mock.calls.filter(([url]) => url.endsWith('/rating'))

describe('kartu rincian rating untuk Middle ke atas', () => {
  it('meminta rincian dan menampilkan tiga dimensi beserta angkanya', async () => {
    const w = await open(DONE())
    expect(ratingCalls()).toEqual([['/documents/7/rating']])
    const text = w.text()
    for (const part of ['Kekerasan', 'Konten seksual', 'Bahasa kasar', '4,2%', '9 paragraf', '0,4%', '1 paragraf', '12,5%', '27 paragraf']) expect(text).toContain(part)
  })

  it('bilah mengikuti persentase dan tidak melewati 100', async () => {
    ratingResponse = () => Promise.resolve({ data: { ...BREAKDOWN, dimensions: BREAKDOWN.dimensions.map((d, i) => ({ ...d, percent: [4.2, 0, 130][i] })) } })
    const w = await open(DONE())
    const widths = w.findAll('[data-test="dimension-bar"]').map((b) => b.attributes('style'))
    expect(widths[0]).toContain('width: 4.2%')
    expect(widths[1]).toContain('width: 0%')
    expect(widths[2]).toContain('width: 100%')
  })

  it('menampilkan alasan rating dan catatan bahasa kasar', async () => {
    const text = (await open(DONE())).text()
    expect(text).toContain('Kekerasan 4,2% paragraf (9 paragraf) mencapai batas Teen: minimal 3% dan 2 paragraf.')
    expect(text).toContain('tidak dihitung dalam rating')
  })

  it('tidak lagi memuat tanda strip placeholder', async () => {
    const w = await open(DONE())
    expect(w.text()).not.toContain('– %')
    expect(w.text()).not.toContain('akan muncul di sini')
  })

  it('menampilkan keadaan memuat selagi menunggu', async () => {
    let finish
    ratingResponse = () => new Promise((resolve) => (finish = resolve))
    const w = await open(DONE())
    expect(w.text()).toContain('Memuat rincian…')
    finish({ data: BREAKDOWN })
    await flushPromises()
    expect(w.text()).not.toContain('Memuat rincian…')
    expect(w.text()).toContain('12,5%')
  })

  it('menampilkan pesan galat bila gagal', async () => {
    ratingResponse = () => Promise.reject({ response: { data: { detail: 'Analisis belum selesai.' } } })
    const w = await open(DONE())
    expect(w.find('[role="alert"]').text()).toBe('Analisis belum selesai.')
  })

  it('memakai pesan bawaan bila server tidak memberi alasan', async () => {
    ratingResponse = () => Promise.reject(new Error('jaringan'))
    const w = await open(DONE())
    expect(w.find('[role="alert"]').text()).toBe('Gagal memuat rincian rating.')
  })

  it('rincian hanya diminta sekali walau halaman memperbarui diri', async () => {
    await open(DONE())
    await vi.advanceTimersByTimeAsync(7000)
    expect(ratingCalls()).toHaveLength(1)
  })

  it('belum diminta selama buku masih diproses', async () => {
    await open(DOC({ status: 'analyzing' }))
    expect(ratingCalls()).toHaveLength(0)
  })

  it('diminta begitu analisis selesai saat halaman dibuka lebih dulu', async () => {
    const w = await open(DOC({ status: 'analyzing', estimated_seconds: 30 }))
    get.mockImplementation((url) => (url.endsWith('/rating') ? ratingResponse() : Promise.resolve({ data: DONE() })))
    await vi.advanceTimersByTimeAsync(3100)
    await flushPromises()
    expect(ratingCalls()).toHaveLength(1)
    expect(w.text()).toContain('27 paragraf')
  })
})

describe('kartu rincian rating untuk akun Standard', () => {
  it('terkunci tanpa data tiruan dan tanpa memanggil server', async () => {
    tier.allowed = false
    const w = await open(DONE())
    expect(ratingCalls()).toHaveLength(0)
    expect(w.text()).toContain('Rincian per dimensi dan alasan rating tersedia di Middle Tier.')
    expect(w.text()).not.toContain('– %')
    expect(w.text()).not.toContain('27 paragraf')
  })
})

describe('tombol Unduh PDF untuk akun di bawah High', () => {
  it('membuka pop-up peningkatan paket, bukan tautan', async () => {
    tier.allowed = false
    closeUpgrade()
    const w = await open(DOC({ status: 'done', rating: 'Teen' }))
    const lock = w.find('[data-test="export-locked"]')
    expect(lock.exists()).toBe(true)
    await lock.trigger('click')
    expect(upgrade).toMatchObject({ open: true, tier: 'high' })
    closeUpgrade()
  })

  it('tidak muncul untuk akun High', async () => {
    tier.allowed = true
    const w = await open(DOC({ status: 'done', rating: 'Teen' }))
    expect(w.find('[data-test="export-locked"]').exists()).toBe(false)
  })
})
