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
  it('menampilkan progres halaman dan persennya', () => {
    const w = card(DOC({ status: 'reading', read_pages: 120, progress: 40 }))
    expect(w.text()).toContain('Membaca halaman 120 dari 300')
    expect(w.find('[data-test="percent"]').text()).toBe('40%')
    const bar = w.find('[role="progressbar"]')
    expect(bar.attributes('aria-valuenow')).toBe('40')
    expect(bar.attributes('aria-valuemax')).toBe('100')
  })

  it('bilah progres mengikuti persentase dari server', () => {
    const w = card(DOC({ status: 'reading', read_pages: 150, progress: 50 }))
    expect(w.find('[data-test="fill"]').attributes('style')).toContain('width: 50%')
  })

  it('tetap tampil sebelum halaman pertama selesai', () => {
    const w = card(DOC({ status: 'reading', read_pages: 0, progress: 0 }))
    expect(w.text()).toContain('Membaca halaman 0 dari 300')
    expect(w.find('[data-test="fill"]').attributes('style')).toContain('width: 0%')
  })

  it('tidak melewati 100 persen', () => {
    const w = card(DOC({ status: 'reading', read_pages: 400, progress: 140 }))
    expect(w.find('[data-test="fill"]').attributes('style')).toContain('width: 100%')
  })

  it('memakai varian ringkas tanpa petunjuk', () => {
    const w = card(DOC({ status: 'reading', read_pages: 5, progress: 2 }))
    expect(w.find('.is-compact').exists()).toBe(true)
    expect(w.find('[data-test="tip"]').exists()).toBe(false)
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

describe('kartu buku yang menunggu atau dianalisis', () => {
  it('menunggu giliran menampilkan 0 persen', () => {
    const w = card(DOC({ status: 'queued', progress: 0 }))
    expect(w.text()).toContain('Menunggu giliran')
    expect(w.find('[data-test="percent"]').text()).toBe('0%')
  })

  it('dianalisis menampilkan persen analisis', () => {
    const w = card(DOC({ status: 'analyzing', progress: 62 }))
    expect(w.text()).toContain('Menganalisis isi buku')
    expect(w.find('[data-test="percent"]').text()).toBe('62%')
    expect(w.find('[role="progressbar"]').attributes('aria-valuenow')).toBe('62')
  })

  it('tanpa angka dari server tampil sebagai keadaan tak tentu', () => {
    const w = card(DOC({ status: 'analyzing', progress: null }))
    expect(w.find('[data-test="percent"]').exists()).toBe(false)
    expect(w.find('[data-test="fill"]').classes()).toContain('is-indeterminate')
  })

  it('tidak menyebut OCR, scan, atau gambar', () => {
    const text = card(DOC({ status: 'analyzing', progress: 10 })).text().toLowerCase()
    for (const word of ['ocr', 'scan', 'gambar']) expect(text).not.toContain(word)
  })
})

describe('kartu dokumen yang bukan novel', () => {
  const other = () => card(DOC({ status: 'not_novel', rating: null, progress: null }))

  it('menampilkan label Bukan novel tanpa bilah progres', () => {
    const w = other()
    expect(w.text()).toContain('Bukan novel')
    expect(w.find('[role="progressbar"]').exists()).toBe(false)
  })

  it('tidak menawarkan Hasil atau Baca', () => {
    const w = other()
    expect(w.text()).not.toContain('Baca')
    expect(w.text()).not.toContain('Hasil')
  })

  it('tetap bisa dibuka dan dihapus', async () => {
    const w = other()
    expect(w.text()).toContain('Lihat')
    await w.find('button').trigger('click')
    expect(w.emitted('delete')).toHaveLength(1)
  })

  it('tidak menampilkan pesan gagal', () => {
    expect(other().text()).not.toContain('Analisis gagal')
  })

  it('tidak menyebut OCR, scan, atau gambar', () => {
    const text = other().text().toLowerCase()
    for (const word of ['ocr', 'scan', 'gambar']) expect(text).not.toContain(word)
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
