// v-reveal：滚动显现指令（AOS 范式的零依赖实现）
// 用法：v-reveal 或 v-reveal="120"（延迟毫秒）。元素进入视口后加 .rv-in 播放上浮显现，只播一次。
// 所有元素共享单个 IntersectionObserver（列表页可能一次挂上千节点，逐元素建 IO 会卡）。
let sharedIO: IntersectionObserver | null = null
const getIO = () => {
  if (!sharedIO) {
    sharedIO = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            e.target.classList.add('rv-in')
            sharedIO!.unobserve(e.target)
          }
        }
      },
      { threshold: 0.12 },
    )
  }
  return sharedIO
}
const observed = new WeakSet<Element>()

export const vReveal = {
  mounted(el: HTMLElement, binding: { value?: number }) {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduced || typeof IntersectionObserver === 'undefined') return
    el.classList.add('rv')
    if (binding.value) el.style.transitionDelay = `${binding.value}ms`
    if (observed.has(el)) return
    getIO().observe(el)
    observed.add(el)
  },
  unmounted(el: HTMLElement) {
    if (sharedIO && observed.has(el)) {
      sharedIO.unobserve(el)
      observed.delete(el)
    }
  },
}

