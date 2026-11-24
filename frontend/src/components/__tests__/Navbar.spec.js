import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('@/lib/auth', () => ({ auth: { user: { name: 'Rana', email: 'rana@example.com' } }, logout: vi.fn() }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

import Navbar from '@/components/Navbar.vue'

const DOC = (o = {}) => ({ id: 3, title: 'Buku Uji', status: 'done', rating: 'Teen', page_count: 20, ...o })

function bar(doc) {
  return mount(Navbar, {
    props: { id: '3', doc },
    global: {
      stubs: {
        Icon: true,
        RatingBadge: true,
        TierChip: true,
        UserAvatar: true,
        Logo: true,
        RouterLink: { props: ['to'], template: '<a><slot /></a>' },
      },
    },
  })
}

const item = (w, text) => w.findAll('a').find((a) => a.text().includes(text))
const LOCKABLE = ['Mode baca', 'Rangkuman', 'Deskripsi tokoh', 'Relasi tokoh']

describe('menu buku untuk dokumen bukan novel', () => {
  it('mengunci mode baca, rangkuman, deskripsi tokoh, dan relasi tokoh', () => {
    const w = bar(DOC({ status: 'not_novel', rating: null }))
    for (const name of LOCKABLE) expect(item(w, name).find('[data-test="lock"]').exists(), name).toBe(true)
    expect(w.findAll('[data-test="lock"]')).toHaveLength(4)
  })

  it('hasil analisis dan profil sensitivitas tidak terkunci', () => {
    const w = bar(DOC({ status: 'not_novel', rating: null }))
    expect(item(w, 'Hasil analisis').find('[data-test="lock"]').exists()).toBe(false)
    expect(item(w, 'Profil sensitivitas').find('[data-test="lock"]').exists()).toBe(false)
  })

  it('menu terkunci tetap tautan yang bisa dibuka dan menjelaskan alasannya', () => {
    const w = bar(DOC({ status: 'not_novel', rating: null }))
    for (const name of LOCKABLE) expect(item(w, name).attributes('title')).toContain('bukan novel')
  })
})

describe('menu buku untuk dokumen lain', () => {
  it.each(['done', 'queued', 'analyzing', 'reading', 'failed'])('tidak ada gembok untuk status %s', (status) => {
    expect(bar(DOC({ status })).find('[data-test="lock"]').exists()).toBe(false)
  })

  it('tidak ada gembok sebelum data buku termuat', () => {
    expect(bar(null).find('[data-test="lock"]').exists()).toBe(false)
  })
})
