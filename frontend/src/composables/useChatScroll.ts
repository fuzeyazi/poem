import { computed, nextTick, readonly, shallowRef, type Ref } from 'vue'

export function useChatScroll(list: Ref<HTMLElement | null>) {
  const following = shallowRef(true)
  const hasUnseen = shallowRef(false)
  const showLatest = computed(() => !following.value && hasUnseen.value)
  function onScroll() {
    const el = list.value
    if (!el) return
    following.value = el.scrollHeight - el.clientHeight - el.scrollTop <= 80
    if (following.value) hasUnseen.value = false
  }
  async function jumpToLatest() {
    following.value = true
    hasUnseen.value = false
    await nextTick()
    if (list.value) list.value.scrollTop = list.value.scrollHeight
  }
  async function contentChanged() {
    if (!following.value) { hasUnseen.value = true; return }
    await nextTick()
    // A scroll event may arrive while Vue updates the streamed content.
    if (following.value && list.value) list.value.scrollTop = list.value.scrollHeight
  }
  return { showLatest: readonly(showLatest), onScroll, contentChanged, jumpToLatest }
}
