import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

let loadSnap

beforeEach(async () => {
  vi.resetModules()
  delete window.snap
  document.head.querySelectorAll('script[data-client-key]').forEach((s) => s.remove())
  ;({ loadSnap } = await import('@/lib/snap'))
})

afterEach(() => {
  delete window.snap
  document.head.querySelectorAll('script[data-client-key]').forEach((s) => s.remove())
})

const scripts = () => [...document.head.querySelectorAll('script[data-client-key]')]

describe('memuat skrip Snap', () => {
  it('langsung selesai bila Snap sudah ada, tanpa menambah skrip', async () => {
    window.snap = { embed: vi.fn() }
    await expect(loadSnap('https://snap.test/snap.js', 'KUNCI')).resolves.toBe(window.snap)
    expect(scripts()).toHaveLength(0)
  })

  it('menambah satu elemen skrip dengan alamat dan kunci klien', () => {
    loadSnap('https://snap.test/snap.js', 'KUNCI')
    const [script] = scripts()
    expect(scripts()).toHaveLength(1)
    expect(script.src).toBe('https://snap.test/snap.js')
    expect(script.getAttribute('data-client-key')).toBe('KUNCI')
  })

  it('selesai dengan objek Snap setelah skrip termuat', async () => {
    const promise = loadSnap('https://snap.test/snap.js', 'KUNCI')
    window.snap = { embed: vi.fn() }
    scripts()[0].onload()
    await expect(promise).resolves.toBe(window.snap)
  })

  it('pemanggilan berikutnya memakai skrip yang sama selama masih memuat', async () => {
    const first = loadSnap('https://snap.test/snap.js', 'KUNCI')
    const second = loadSnap('https://snap.test/snap.js', 'KUNCI')
    expect(second).toBe(first)
    expect(scripts()).toHaveLength(1)
    window.snap = {}
    scripts()[0].onload()
    await first
  })

  it('gagal bila skrip termuat tetapi tidak menyediakan Snap', async () => {
    const promise = loadSnap('https://snap.test/snap.js', 'KUNCI')
    scripts()[0].onload()
    await expect(promise).rejects.toThrow()
  })

  it('gagal bila skrip tidak bisa dimuat, melepas elemennya, dan boleh dicoba lagi', async () => {
    const promise = loadSnap('https://snap.test/snap.js', 'KUNCI')
    scripts()[0].onerror()
    await expect(promise).rejects.toThrow()
    expect(scripts()).toHaveLength(0)
    loadSnap('https://snap.test/snap.js', 'KUNCI')
    expect(scripts()).toHaveLength(1)
  })
})
