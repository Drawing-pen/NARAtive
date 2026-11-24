import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import NotNovelNotice from '@/components/NotNovelNotice.vue'

function notice(props = {}) {
  return mount(NotNovelNotice, {
    props: { id: '3', ...props },
    global: { stubs: { Icon: true, RouterLink: { props: ['to'], template: '<a :data-to="JSON.stringify(to)"><slot /></a>' } } },
  })
}

describe('pesan dokumen bukan novel', () => {
  it('mengatakan dengan jelas bahwa dokumen ini bukan novel', () => {
    expect(notice().text()).toContain('Dokumen ini bukan novel')
  })

  it('menjelaskan alasan dan bahwa kuota tidak terpakai', () => {
    const text = notice().text()
    expect(text).toContain('artikel, makalah, atau catatan')
    expect(text).toContain('Kuota analisismu tidak terpakai')
  })

  it('tidak menyebut OCR, scan, atau gambar', () => {
    const text = notice().text().toLowerCase()
    for (const word of ['ocr', 'scan', 'gambar']) expect(text).not.toContain(word)
  })

  it('diumumkan sebagai status untuk pembaca layar', () => {
    expect(notice().find('[role="status"]').exists()).toBe(true)
  })

  it('menautkan ke hasil analisis buku yang sama secara bawaan', () => {
    const link = notice({ id: '9' }).find('a')
    expect(link.text()).toContain('Lihat hasil analisis')
    expect(JSON.parse(link.attributes('data-to'))).toEqual({ name: 'document', params: { id: '9' } })
  })

  it('tanpa tautan bila diminta', () => {
    expect(notice({ link: false }).find('a').exists()).toBe(false)
  })
})
