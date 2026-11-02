import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import UserAvatar from '@/components/UserAvatar.vue'

const show = (name, size) => mount(UserAvatar, { props: { name, size }, global: { stubs: { Icon: true } } })

describe('UserAvatar', () => {
  it('shows the first letters of the first two words', () => {
    expect(show('rana afifah dzikro').text()).toBe('RA')
  })

  it('shows one letter for a single word and ignores extra spaces', () => {
    expect(show('  Rana  ').text()).toBe('R')
  })

  it('falls back to a user icon without a name', () => {
    const w = show('')
    expect(w.text()).toBe('')
    expect(w.find('icon-stub').exists()).toBe(true)
  })

  it('is hidden from screen readers and sized by the prop', () => {
    const w = show('Rana', 'lg')
    expect(w.attributes('aria-hidden')).toBe('true')
    expect(w.classes()).toContain('size-16')
  })

  it('uses the medium size for an unknown size', () => {
    expect(show('Rana', 'raksasa').classes()).toContain('size-10')
  })
})
