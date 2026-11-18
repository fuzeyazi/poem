/**
 * 高清诗词卡片图片导出工具
 * cardExporter.ts
 */
import { toPng, toBlob } from 'html-to-image'

export interface ExportCardOptions {
  pixelRatio?: number
  backgroundColor?: string
  quality?: number
}

/**
 * 格式化导出的文件名：诗词卡片-{author}-{title}.png
 * 过滤操作系统非法字符
 */
export function formatCardFilename(author?: string, title?: string): string {
  const safeAuthor = (author || '佚名').replace(/[\\/:*?"<>|\r\n\t]/g, '').trim() || '佚名'
  const safeTitle = (title || '无题').replace(/[\\/:*?"<>|\r\n\t]/g, '').trim() || '无题'
  return `诗词卡片-${safeAuthor}-${safeTitle}.png`
}

/**
 * 触发浏览器原生下载
 */
export function triggerDownload(url: string, filename: string): void {
  if (typeof document === 'undefined') return
  const link = document.createElement('a')
  link.download = filename.endsWith('.png') ? filename : `${filename}.png`
  link.href = url
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  setTimeout(() => {
    document.body.removeChild(link)
  }, 100)
}

/**
 * 等待字体加载与微任务渲染稳定
 */
export async function waitFontsAndRender(): Promise<void> {
  if (typeof document !== 'undefined' && 'fonts' in document) {
    try {
      await document.fonts.ready
    } catch {
      // 容错降级
    }
  }
  // 双重 rAF 确保样式与 SVG 滤镜就绪
  await new Promise(resolve => {
    if (typeof requestAnimationFrame !== 'undefined') {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => setTimeout(resolve, 50))
      })
    } else {
      setTimeout(resolve, 50)
    }
  })
}

/**
 * 将指定 DOM 节点导出为高清 PNG 并触发下载
 * 默认使用 3x 超高清像素比
 */
export async function exportCardImage(
  element: HTMLElement,
  filename = '诗词卡片.png',
  options: ExportCardOptions = {}
): Promise<string> {
  if (!element) {
    throw new Error('导出失败：目标 DOM 节点不存在')
  }

  await waitFontsAndRender()

  const pixelRatio = options.pixelRatio ?? 3
  const config = {
    pixelRatio,
    cacheBust: true,
    backgroundColor: options.backgroundColor,
    quality: options.quality ?? 0.95
  }

  try {
    const dataUrl = await toPng(element, config)
    triggerDownload(dataUrl, filename)
    return dataUrl
  } catch (err: any) {
    console.error('html-to-image 导出异常，尝试二次重试:', err)
    // 降级使用 2x 重试一次
    const fallbackDataUrl = await toPng(element, { ...config, pixelRatio: 2 })
    triggerDownload(fallbackDataUrl, filename)
    return fallbackDataUrl
  }
}

/**
 * 获取卡片 Blob 数据（便于复制剪贴板或上传）
 */
export async function getCardBlob(
  element: HTMLElement,
  options: ExportCardOptions = {}
): Promise<Blob | null> {
  if (!element) return null
  await waitFontsAndRender()
  return await toBlob(element, {
    pixelRatio: options.pixelRatio ?? 3,
    cacheBust: true
  })
}
