import MarkdownIt from 'markdown-it'

const md = new MarkdownIt('commonmark', { html: false, linkify: false, typographer: false, breaks: false })
md.disable(['fence', 'code', 'lheading', 'hr', 'html_block', 'html_inline', 'reference', 'entity'])

const level = (token) => Math.min(Math.max(Number(token.tag.slice(1)), 3), 6)

md.renderer.rules.heading_open = (tokens, index) => `<h${level(tokens[index])}>`
md.renderer.rules.heading_close = (tokens, index) => `</h${level(tokens[index])}>\n`
md.renderer.rules.link_open = () => ''
md.renderer.rules.link_close = () => ''
md.renderer.rules.image = () => ''
md.renderer.rules.code_inline = (tokens, index) => md.utils.escapeHtml(tokens[index].content)

export function renderMarkdown(source) {
  return source ? md.render(source) : ''
}
