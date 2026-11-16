import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import BookCard from '@/components/BookCard.vue'
import SeriesCard from '@/components/SeriesCard.vue'

const DOC = (o = {}) => ({
  id: 7, title: 'Buku Uji', status: 'done', rating: 'Teen', page_count: 300, read_pages: 0, failure_reason: null,
  created_at: '2026-11-01T08:00:00', has_cover: false, ...o,
})

function card(doc) {
  return mount(BookCard, {
    props: { doc },
    global: { stubs: { Icon: true, RouterLink: { props: ['to'], template: '<a><slot /></a>' }, AuthImage: { template: '<div><slot /></div>' } } },
  })
}

describe('kartu buku yang sedang dibaca', () => {
  it('menampilkan progres halaman', () => {
    const w = card(DOC({ status: 'reading', read_pages: 120 }))
    expect(w.text()).toContain('Membaca halaman 120 dari 300')
    const bar = w.find('[role="progressbar"]')
    expect(bar.attributes('aria-valuenow')).toBe('120')
    expect(bar.attributes('aria-valuemax')).toBe('300')
  })

  it('bilah progres mengikuti persentase halaman', () => {
    const w = card(DOC({ status: 'reading', read_pages: 150 }))
    expect(w.find('[data-test="read-bar"]').attributes('style')).toContain('width: 50%')
  })

  it('tetap tampil sebelum halaman pertama selesai', () => {
    const w = card(DOC({ status: 'reading', read_pages: 0 }))
    expect(w.text()).toContain('Membaca halaman 0 dari 300')
    expect(w.find('[data-test="read-bar"]').attributes('style')).toContain('width: 0%')
  })

  it('tidak melewati 100 persen', () => {
    const w = card(DOC({ status: 'reading', read_pages: 400 }))
    expect(w.find('[data-test="read-bar"]').attributes('style')).toContain('width: 100%')
  })

  it('menawarkan lihat progres, bukan Hasil atau Baca', () => {
    const w = card(DOC({ status: 'reading', read_pages: 5 }))
    expect(w.text()).toContain('Lihat progres')
    expect(w.text()).not.toContain('Baca')
  })

  it('tidak menyebut OCR, scan, atau gambar di mana pun', () => {
    const text = card(DOC({ status: 'reading', read_pages: 5 })).text().toLowerCase()
    for (const word of ['ocr', 'scan', 'gambar']) expect(text).not.toContain(word)
  })

  it('label status menyebut membaca berkas', () => {
    expect(card(DOC({ status: 'reading' })).text()).toContain('Membaca berkas')
  })
})

describe('kartu buku yang gagal', () => {
  it('menampilkan alasan dari server', () => {
    const w = card(DOC({ status: 'failed', failure_reason: 'Berkas ini tidak berisi teks yang dapat dibaca.' }))
    expect(w.text()).toContain('Berkas ini tidak berisi teks yang dapat dibaca.')
  })

  it('memakai pesan lama bila tidak ada alasan', () => {
    expect(card(DOC({ status: 'failed' })).text()).toContain('Analisis gagal. Unggah ulang file ini.')
  })

  it('tetap bisa dihapus', async () => {
    const w = card(DOC({ status: 'failed', failure_reason: 'x' }))
    await w.find('button').trigger('click')
    expect(w.emitted('delete')).toHaveLength(1)
  })
})

describe('kartu buku selesai', () => {
  it('tetap menampilkan Hasil dan Baca', () => {
    const w = card(DOC())
    expect(w.text()).toContain('Hasil')
    expect(w.text()).toContain('Baca')
    expect(w.find('[role="progressbar"]').exists()).toBe(false)
  })
})

describe('kartu seri', () => {
  const group = (statuses) => ({ id: 1, name: 'Seri Uji', books: statuses.map((status, i) => DOC({ id: i + 1, status })) })
  const seri = (g) => mount(SeriesCard, { props: { group: g }, global: { stubs: { Icon: true } } })

  it('menghitung buku yang sedang dibaca sebagai sedang diproses', () => {
    expect(seri(group(['done', 'reading'])).text()).toContain('1 buku sedang diproses')
  })

  it('menghitung buku yang sedang dianalisis atau antre juga', () => {
    expect(seri(group(['reading', 'queued', 'analyzing'])).text()).toContain('3 buku sedang diproses')
  })

  it('semua selesai', () => {
    expect(seri(group(['done', 'done'])).text()).toContain('Semua buku selesai dianalisis')
  })
})
