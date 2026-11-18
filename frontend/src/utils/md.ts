/* 轻量 Markdown 渲染：AI 回复美化用。
   先整体 HTML 转义防注入，再做有限转换：**加粗** / *斜体* / # 标题 / - 列表 / 1. 列表 / > 引用 / `代码`。
   流式期间部分符号会短暂原样显示，收帧后即归位。 */
const escapeHtml = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

const inline = (t: string) =>
  t
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')

export function renderMdLite(src: string): string {
  if (!src) return ''
  const out: string[] = []
  let inList = false
  let inOl = false
  let inQuote = false
  const closeAll = () => {
    if (inList) { out.push('</ul>'); inList = false }
    if (inOl) { out.push('</ol>'); inOl = false }
    if (inQuote) { out.push('</blockquote>'); inQuote = false }
  }
  for (const raw of escapeHtml(src).split(/\r?\n/)) {
    const line = raw.trimEnd()
    const h = line.match(/^(#{1,4})\s+(.*)$/)
    const ul = line.match(/^\s*[-*•]\s+(.*)$/)
    const ol = line.match(/^\s*\d+[.、]\s+(.*)$/)
    const bq = line.match(/^>\s?(.*)$/)
    if (!line.trim()) { closeAll(); continue }
    if (h) { closeAll(); out.push(`<h4 class="md-h">${inline(h[2])}</h4>`); continue }
    if (ul) { if (inOl || inQuote) closeAll(); if (!inList) { out.push('<ul class="md-ul">'); inList = true } out.push(`<li>${inline(ul[1])}</li>`); continue }
    if (ol) { if (inList || inQuote) closeAll(); if (!inOl) { out.push('<ol class="md-ol">'); inOl = true } out.push(`<li>${inline(ol[1])}</li>`); continue }
    if (bq) { if (inList) closeAll(); if (!inQuote) { out.push('<blockquote class="md-quote">'); inQuote = true } out.push(`<p>${inline(bq[1])}</p>`); continue }
    if (inList || inQuote) closeAll()
    out.push(`<p>${inline(line)}</p>`)
  }
  closeAll()
  return out.join('')
}
