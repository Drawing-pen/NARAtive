import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const get = vi.fn()

vi.mock('@/lib/api', () => ({
  default: { get: (...args) => get(...args) },
  errorMessage: (e, fallback) => e?.response?.data?.detail ?? fallback,
}))

import AdminPage from '@/pages/AdminPage.vue'

function days(key, last) {
  return Array.from({ length: 30 }, (_, i) => ({ date: `2026-10-${String(i + 1).padStart(2, '0')}`, [key]: i === 29 ? last : 0 }))
}

const DATA = {
  users: { total: 42, inactive: 2, per_tier: { free: 30, middle: 8, high: 2 }, signups: days('count', 5) },
  revenue: {
    paid_total: 1_250_000,
    paid_this_month: 350_000,
    by_status: { pending: 1, paid: 9, failed: 2, expired: 3, cancelled: 0 },
    by_plan: { middle: { count: 6, amount: 174_000 }, high: { count: 3, amount: 177_000 }, pay_per_check: { count: 0, amount: 0 } },
    per_day: days('amount', 59_000),
  },
  documents: {
    total: 77,
    by_status: { uploaded: 0, queued: 1, analyzing: 2, done: 70, failed: 4 },
    uploads: days('count', 3),
    failure_reasons: [{ reason: 'PDF terenkripsi', count: 3 }, { reason: 'Teks tidak terbaca', count: 1 }],
    summary: { done: 20, partial: 2, failed: 1 },
    characters: { done: 15, partial: 1, failed: 0 },
  },
  quota: { at_limit: 7 },
  generated_at: '2026-11-16T03:00:00',
}

async function open() {
  const w = mount(AdminPage, { global: { stubs: { Icon: true } } })
  await flushPromises()
  return w
}

beforeEach(() => {
  get.mockReset()
  get.mockResolvedValue({ data: DATA })
})

describe('AdminPage', () => {
  it('memuat dari endpoint admin', async () => {
    await open()
    expect(get).toHaveBeenCalledWith('/admin/overview')
  })

  it('menampilkan keadaan memuat', () => {
    get.mockReturnValue(new Promise(() => {}))
    const w = mount(AdminPage, { global: { stubs: { Icon: true } } })
    expect(w.text()).toContain('Memuat')
  })

  it('kartu ringkas memuat angka utama', async () => {
    const text = (await open()).text()
    expect(text).toContain('42')
    expect(text).toContain('Rp 350.000')
    expect(text).toContain('77')
    expect(text).toContain('7')
  })

  it('sebaran paket tampil', async () => {
    const text = (await open()).text()
    expect(text).toContain('Standard')
    expect(text).toContain('30')
    expect(text).toContain('Middle')
    expect(text).toContain('High')
  })

  it('tiga grafik batang 30 hari dengan label aksesibel', async () => {
    const w = await open()
    const charts = w.findAll('[role="img"]')
    expect(charts).toHaveLength(3)
    expect(charts[0].attributes('aria-label')).toContain('Pendaftar')
    expect(charts[0].attributes('aria-label')).toContain('5')
    expect(charts[1].attributes('aria-label')).toContain('Rp 59.000')
    expect(charts[2].attributes('aria-label')).toContain('Unggahan')
    expect(charts[0].findAll('[data-test="bar"]')).toHaveLength(30)
  })

  it('tabel status transaksi dan dokumen', async () => {
    const text = (await open()).text()
    expect(text).toContain('Dibayar')
    expect(text).toContain('Menunggu')
    expect(text).toContain('Selesai')
    expect(text).toContain('Gagal')
    expect(text).toContain('70')
  })

  it('alasan gagal teratas tampil dengan jumlahnya', async () => {
    const text = (await open()).text()
    expect(text).toContain('PDF terenkripsi')
    expect(text).toContain('Teks tidak terbaca')
  })

  it('tanpa alasan gagal menampilkan keterangan kosong', async () => {
    get.mockResolvedValue({ data: { ...DATA, documents: { ...DATA.documents, failure_reasons: [] } } })
    expect((await open()).text()).toContain('Belum ada e-book yang gagal.')
  })

  it('403 menampilkan pesan khusus admin', async () => {
    get.mockRejectedValue({ response: { status: 403, data: { detail: 'Fitur ini khusus admin.' } } })
    expect((await open()).text()).toContain('Halaman ini khusus admin.')
  })

  it('galat lain menampilkan pesan gagal', async () => {
    get.mockRejectedValue(new Error('mati'))
    expect((await open()).text()).toContain('Gagal mengambil data admin.')
  })

  it('tombol muat ulang mengambil data lagi', async () => {
    const w = await open()
    await w.findAll('button').find((b) => b.text().includes('Muat ulang')).trigger('click')
    await flushPromises()
    expect(get).toHaveBeenCalledTimes(2)
  })

  it('tidak menampilkan data pribadi', async () => {
    const w = await open()
    expect(w.html()).not.toMatch(/@|email|\.pdf/i)
  })
})
