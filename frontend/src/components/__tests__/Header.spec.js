import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

const state = { admin: false }

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/lib/auth', () => ({
  auth: { user: { name: 'Rana', email: 'r@example.com', role: 'user' } },
  isLoggedIn: () => true,
  isAdmin: () => state.admin,
  logout: vi.fn(),
  tierKey: () => 'standard',
}))

import Header from '@/components/Header.vue'

const open = () =>
  mount(Header, {
    global: { stubs: { Icon: true, Logo: true, TierChip: true, UserAvatar: true, RouterLink: { props: ['to'], template: '<a :data-to="JSON.stringify(to)"><slot /></a>' } } },
  })

beforeEach(() => {
  state.admin = false
})

describe('Header tautan admin', () => {
  it('tersembunyi untuk pengguna biasa', () => {
    expect(open().text()).not.toContain('Admin')
  })

  it('tampil untuk admin dan menuju rute admin', () => {
    state.admin = true
    const link = open().findAll('a').find((a) => a.text() === 'Admin')
    expect(link).toBeTruthy()
    expect(link.attributes('data-to')).toContain('admin')
  })
})
