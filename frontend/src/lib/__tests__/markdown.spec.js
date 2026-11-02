import { describe, expect, it } from 'vitest'

import { renderMarkdown } from '@/lib/markdown'

const dom = (markdown) => {
  const root = document.createElement('div')
  root.innerHTML = renderMarkdown(markdown)
  return root
}

describe('formatting that is allowed', () => {
  it('renders bold and italic', () => {
    const root = dom('Kata **tebal** dan *miring* serta _miring lain_.')
    expect(root.querySelector('strong').textContent).toBe('tebal')
    expect([...root.querySelectorAll('em')].map((e) => e.textContent)).toEqual(['miring', 'miring lain'])
  })

  it('renders bold and italic together', () => {
    expect(dom('***sangat***').querySelector('strong em, em strong')).not.toBeNull()
  })

  it('renders a paragraph', () => {
    expect(dom('Satu kalimat.').querySelectorAll('p')).toHaveLength(1)
  })

  it('renders several paragraphs of one block', () => {
    expect(dom('Paragraf satu.\n\nParagraf dua.').querySelectorAll('p')).toHaveLength(2)
  })

  it('renders unordered and ordered list items', () => {
    expect(dom('- butir satu').querySelectorAll('ul > li')).toHaveLength(1)
    expect(dom('1. butir satu').querySelectorAll('ol > li')).toHaveLength(1)
  })

  it('keeps the number of an ordered list item', () => {
    expect(dom('3. butir tiga').querySelector('ol').getAttribute('start')).toBe('3')
  })

  it('renders a quote', () => {
    expect(dom('> kutipan penting').querySelector('blockquote').textContent.trim()).toBe('kutipan penting')
  })

  it('escaped markup characters show up as plain characters', () => {
    expect(dom('hitung 2\\*3\\*4 sekarang').textContent.trim()).toBe('hitung 2*3*4 sekarang')
  })
})

describe('headings', () => {
  it.each([
    ['# Judul', 'H3'],
    ['## Judul', 'H3'],
    ['### Judul', 'H3'],
    ['#### Judul', 'H4'],
    ['##### Judul', 'H5'],
    ['###### Judul', 'H6'],
  ])('%s becomes %s so it never competes with the chapter title', (source, tag) => {
    const heading = dom(source).querySelector('h1, h2, h3, h4, h5, h6')
    expect(heading.tagName).toBe(tag)
    expect(heading.textContent).toBe('Judul')
  })

  it('never produces a level one or two heading', () => {
    expect(dom('# a\n\n## b').querySelectorAll('h1, h2')).toHaveLength(0)
  })
})

describe('safety: the book text is untrusted input', () => {
  it('shows raw HTML as text', () => {
    const root = dom('<script>alert(1)</script> halo')
    expect(root.querySelector('script')).toBeNull()
    expect(root.textContent).toContain('<script>alert(1)</script>')
  })

  it('does not run event handlers from raw tags', () => {
    const root = dom('<img src=x onerror="alert(1)"> dan <div onclick="alert(1)">klik</div>')
    expect(root.querySelector('img')).toBeNull()
    expect(root.querySelector('[onclick], [onerror]')).toBeNull()
  })

  it('does not render a raw HTML block', () => {
    expect(dom('<iframe src="https://jahat.example"></iframe>').querySelector('iframe')).toBeNull()
  })

  it('does not render links, only their text', () => {
    const root = dom('Buka [tautan ini](https://jahat.example/x) sekarang')
    expect(root.querySelector('a')).toBeNull()
    expect(root.textContent).toContain('tautan ini')
    expect(root.innerHTML).not.toContain('jahat.example')
  })

  it('does not render javascript links', () => {
    const root = dom('[klik](javascript:alert(1))')
    expect(root.querySelector('a, [href]')).toBeNull()
  })

  it('does not turn plain addresses into links', () => {
    expect(dom('kunjungi https://contoh.com dan www.contoh.com').querySelector('a')).toBeNull()
  })

  it('does not render images', () => {
    const root = dom('Sebelum ![gambar](https://jahat.example/a.png) sesudah')
    expect(root.querySelector('img')).toBeNull()
    expect(root.innerHTML).not.toContain('jahat.example')
  })

  it('does not render tables or code blocks as structure', () => {
    const root = dom('|a|b|\n|-|-|\n|1|2|\n\n```\nkode\n```')
    expect(root.querySelector('table, pre, code')).toBeNull()
  })

  it('escapes angle brackets that were escaped on purpose', () => {
    const root = dom('tanda \\<kurung\\> sudut')
    expect(root.querySelector('kurung')).toBeNull()
    expect(root.textContent).toContain('<kurung>')
  })

  it('produces only the allowed tags', () => {
    const allowed = ['H3', 'P', 'STRONG', 'EM', 'UL', 'OL', 'LI', 'BLOCKQUOTE']
    const root = dom(['# a', '**b** *c*', '- d', '1. e', '> f', '[g](h) ![i](j) <u>k</u> `l`'].join('\n\n'))
    const found = [...root.querySelectorAll('*')].map((e) => e.tagName)
    expect(found.length).toBeGreaterThan(5)
    expect(found.every((tag) => allowed.includes(tag))).toBe(true)
  })
})

describe('edge cases', () => {
  it('returns an empty string for empty input', () => {
    expect(renderMarkdown('')).toBe('')
    expect(renderMarkdown(null)).toBe('')
    expect(renderMarkdown(undefined)).toBe('')
  })

  it('handles very long text', () => {
    const long = 'kata '.repeat(5000)
    expect(dom(long).textContent.length).toBeGreaterThan(20000)
  })
})
