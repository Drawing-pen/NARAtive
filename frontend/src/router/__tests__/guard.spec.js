import { beforeEach, describe, expect, it, vi } from 'vitest'

const state = { loggedIn: true, admin: false }

vi.mock('@/lib/auth', () => ({ isLoggedIn: () => state.loggedIn, isAdmin: () => state.admin }))
vi.mock('@/pages/AdminPage.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/pages/HomePage.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/pages/AuthPage.vue', () => ({ default: { template: '<div />' } }))

import router from '@/router'

beforeEach(async () => {
  state.loggedIn = true
  state.admin = false
  await router.push('/')
})

describe('rute admin', () => {
  it('bukan admin diarahkan ke beranda', async () => {
    await router.push('/admin')
    expect(router.currentRoute.value.name).toBe('home')
  })

  it('admin boleh masuk', async () => {
    state.admin = true
    await router.push('/admin')
    expect(router.currentRoute.value.name).toBe('admin')
  })

  it('belum masuk diarahkan ke masuk', async () => {
    state.loggedIn = false
    await router.push('/admin')
    expect(router.currentRoute.value.name).toBe('login')
  })
})
