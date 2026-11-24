import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const get = vi.fn()

vi.mock('@/lib/api', () => ({
  default: { get: (...args) => get(...args) },
  errorMessage: (e, fallback) => e?.response?.data?.detail ?? fallback,
}))

import InvoicePage from '@/pages/InvoicePage.vue'

const INVOICE = (o = {}) => ({
  number: 'NAR-1-aaaa', status: 'paid',
  issued_at: '2026-10-29T03:03:00', due_at: '2026-10-30T03:03:00', paid_at: '2026-10-29T10:03:00',
  customer_name: 'Rana Dzikro', customer_email: 'rana@example.com', method: 'Virtual Account BCA',
  items: [{ no: 1, name: 'Paket Middle (30 hari)', unit_price: 29000, quantity: 1, total: 29000 }],
  subtotal: 29000, total: 29000, ...o,
})
const failure = (status, detail) => Object.assign(new Error('x'), { response: { status, data: { detail } } })

let outcome

async function open(id = 'NAR-1-aaaa') {
  get.mockImplementation(async (url) => {
    if (url.endsWith('/invoice.pdf')) {
      if (outcome.pdf instanceof Error) throw outcome.pdf
      return { data: new Blob(['%PDF-1.4'], { type: 'application/pdf' }) }
    }
    if (outcome.invoice instanceof Error) throw outcome.invoice
    return { data: outcome.invoice }
  })
  const wrapper = mount(InvoicePage, {
    props: { orderId: id },
    global: { stubs: { Icon: true, RouterLink: { props: ['to'], template: '<a :data-to="JSON.stringify(to)"><slot /></a>' } } },
  })
  await flushPromises()
  return wrapper
}

const button = (w, text) => w.findAll('button').find((b) => b.text().includes(text))

beforeEach(() => {
  get.mockReset()
  outcome = { invoice: INVOICE(), pdf: null }
  URL.createObjectURL = vi.fn(() => 'blob:invoice')
  URL.revokeObjectURL = vi.fn()
})

describe('isi invoice', () => {
  it('meminta invoice milik nomor pesanan di alamat', async () => {
    await open('NAR-7-zzzz')
    expect(get).toHaveBeenCalledWith('/billing/transactions/NAR-7-zzzz/invoice')
  })

  it('menampilkan kop dengan logo NARAtive, judul, dan lencana terbayar', async () => {
    const w = await open()
    const logo = w.find('header img')
    expect(logo.exists()).toBe(true)
    expect(logo.attributes('alt')).toContain('NARAtive')
    expect(w.text()).toContain('Analisis rating konten e-book')
    expect(w.text()).toContain('INVOICE')
    expect(w.text()).toContain('TERBAYAR')
  })

  it('menampilkan siapa yang ditagih dan nomor invoice', async () => {
    const w = await open()
    expect(w.text()).toContain('Ditagihkan kepada')
    expect(w.text()).toContain('Rana Dzikro')
    expect(w.text()).toContain('rana@example.com')
    expect(w.text()).toContain('NAR-1-aaaa')
  })

  it('menampilkan tiga tanggal', async () => {
    const w = await open()
    for (const label of ['Tanggal Invoice', 'Batas Pembayaran', 'Tanggal Terbayar']) expect(w.text()).toContain(label)
    expect(w.text()).toContain('2026')
  })

  it('menampilkan hanya nama metode pembayaran', async () => {
    const w = await open()
    expect(w.text()).toContain('Informasi pembayaran')
    expect(w.text()).toContain('Virtual Account BCA')
  })

  it('menampilkan tabel item dengan harga satuan, jumlah, dan total', async () => {
    const w = await open()
    const row = w.find('[data-test="item"]').text()
    for (const part of ['1', 'Paket Middle (30 hari)', 'Rp 29.000']) expect(row).toContain(part)
  })

  it('menampilkan jumlah dan harga satuan untuk analisis tambahan', async () => {
    outcome.invoice = INVOICE({
      items: [{ no: 1, name: 'Analisis tambahan (pay-per-check)', unit_price: 5000, quantity: 3, total: 15000 }], subtotal: 15000, total: 15000,
    })
    const w = await open()
    const row = w.find('[data-test="item"]').text()
    expect(row).toContain('Rp 5.000')
    expect(row).toContain('3')
    expect(row).toContain('Rp 15.000')
  })

  it('menampilkan subtotal dan total bayar', async () => {
    const w = await open()
    expect(w.find('[data-test="subtotal"]').text()).toContain('Rp 29.000')
    expect(w.find('[data-test="total"]').text()).toContain('Rp 29.000')
    expect(w.text()).toContain('Total Bayar')
  })

  it('tidak menyebut biaya yang tidak dipungut', async () => {
    const text = (await open()).text()
    expect(text).not.toContain('Biaya Layanan')
    expect(text).not.toContain('Biaya Administrasi')
  })
})

describe('keadaan halaman', () => {
  it('menampilkan keadaan memuat lebih dulu', () => {
    get.mockImplementation(() => new Promise(() => {}))
    const w = mount(InvoicePage, { props: { orderId: 'x' }, global: { stubs: { Icon: true, RouterLink: true } } })
    expect(w.text()).toContain('Memuat invoice')
  })

  it('nomor pesanan tidak dikenal tampil sebagai tidak ditemukan', async () => {
    outcome.invoice = failure(404, 'Transaksi tidak ditemukan.')
    const w = await open()
    expect(w.text()).toContain('Invoice tidak ditemukan')
    expect(w.text()).not.toContain('TERBAYAR')
  })

  it('pembayaran yang belum berhasil menampilkan alasannya dan jalan kembali', async () => {
    outcome.invoice = failure(409, 'Invoice hanya tersedia untuk pembayaran yang berhasil.')
    const w = await open()
    expect(w.text()).toContain('Invoice hanya tersedia untuk pembayaran yang berhasil.')
    expect(JSON.parse(w.find('a').attributes('data-to'))).toEqual({ name: 'profile', hash: '#riwayat' })
  })

  it('gangguan lain menawarkan coba lagi yang memuat ulang', async () => {
    outcome.invoice = failure(500, undefined)
    const w = await open()
    expect(w.text()).toContain('Gagal memuat invoice')
    outcome.invoice = INVOICE()
    await button(w, 'Coba lagi').trigger('click')
    await flushPromises()
    expect(w.text()).toContain('TERBAYAR')
  })
})

describe('tombol dan tautan', () => {
  it('menautkan kembali ke riwayat', async () => {
    const w = await open()
    const link = w.findAll('a').find((a) => a.text().includes('Kembali ke riwayat'))
    expect(JSON.parse(link.attributes('data-to'))).toEqual({ name: 'profile', hash: '#riwayat' })
  })

  it('mengunduh PDF lewat blob dengan nama berkas dari nomor pesanan', async () => {
    let fileName = null
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () {
      fileName = this.getAttribute('download')
    })
    const w = await open()
    await button(w, 'Unduh PDF').trigger('click')
    await flushPromises()
    expect(get).toHaveBeenCalledWith('/billing/transactions/NAR-1-aaaa/invoice.pdf', { responseType: 'blob' })
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1)
    expect(click).toHaveBeenCalledTimes(1)
    expect(fileName).toBe('Invoice NARAtive NAR-1-aaaa.pdf')
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:invoice')
    click.mockRestore()
  })

  it('gagal mengunduh menampilkan pesan dan tombol bisa dipakai lagi', async () => {
    outcome.pdf = failure(500, undefined)
    const w = await open()
    await button(w, 'Unduh PDF').trigger('click')
    await flushPromises()
    expect(w.find('[role="alert"]').text()).toContain('Gagal mengunduh invoice.')
    expect(button(w, 'Unduh PDF').attributes('disabled')).toBeUndefined()
  })

  it('tidak menyebut OCR, scan, atau gambar', async () => {
    const text = (await open()).text().toLowerCase()
    for (const word of ['ocr', 'scan', 'gambar']) expect(text).not.toContain(word)
  })
})
