import { afterEach, describe, expect, it } from 'vitest'
import { auth, isAdmin } from '@/lib/auth'

afterEach(() => {
  auth.user = null
})

describe('isAdmin', () => {
  it('benar hanya untuk peran admin', () => {
    auth.user = { role: 'admin' }
    expect(isAdmin()).toBe(true)
    auth.user = { role: 'user' }
    expect(isAdmin()).toBe(false)
    auth.user = null
    expect(isAdmin()).toBe(false)
  })
})
