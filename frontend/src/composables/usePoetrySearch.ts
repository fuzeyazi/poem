import { computed, onScopeDispose, readonly, shallowRef, watch, type Ref } from 'vue'
import { getPoemByTitle, getPoemPage, getPoemsByDynasty } from '@/api/poetry'
import type { Poem } from '@/api/types'

export interface PoetrySearchConditions { q: string; dynasty: string; page: number }
interface SearchSnapshot { records: Poem[]; total: number; scroll: number }
// The bounded visit cache preserves document height during back navigation.
const visits = new Map<string, SearchSnapshot>()
const keyFor = (conditions: PoetrySearchConditions) => JSON.stringify(conditions)

export function usePoetrySearch(conditions: Readonly<Ref<PoetrySearchConditions>>) {
  const initial = visits.get(keyFor(conditions.value))
  const records = shallowRef<Poem[]>(initial?.records || [])
  const total = shallowRef(initial?.total || 0)
  const pending = shallowRef(false)
  const error = shallowRef('')
  const hasResult = shallowRef(!!initial)
  const restoredScroll = initial?.scroll || 0
  let epoch = 0
  const load = async () => {
    const current = ++epoch
    const criteria = { ...conditions.value }
    const key = keyFor(criteria)
    const cached = visits.get(key)
    if (cached) { records.value = cached.records; total.value = cached.total; hasResult.value = true }
    pending.value = true; error.value = ''
    try {
      const result = criteria.q
        ? await getPoemByTitle(criteria.q, criteria.page, 4)
        : criteria.dynasty ? await getPoemsByDynasty(criteria.dynasty, criteria.page, 4) : await getPoemPage(criteria.page, 4)
      if (current !== epoch) return
      const seen = new Set<string>()
      records.value = (result?.records || []).filter(poem => {
        const identity = `${poem.title}|${poem.writer}`
        if (!poem.title || seen.has(identity)) return false
        seen.add(identity); return true
      })
      total.value = result?.total || 0; hasResult.value = true
      visits.set(key, { records: records.value, total: total.value, scroll: cached?.scroll || 0 })
      if (visits.size > 10) visits.delete(visits.keys().next().value!)
    } catch {
      if (current === epoch) error.value = hasResult.value ? '更新失败，下方保留上次结果，请重试。' : '诗词加载失败，请重试。'
    }
    finally { if (current === epoch) pending.value = false }
  }
  const rememberScroll = (scroll: number) => {
    if (!hasResult.value) return
    // A failed refresh still owns the visible records the reader is returning to.
    visits.set(keyFor(conditions.value), { records: records.value, total: total.value, scroll })
    if (visits.size > 10) visits.delete(visits.keys().next().value!)
  }
  watch(conditions, load, { immediate: true })
  onScopeDispose(() => { epoch++ })
  return {
    records: readonly(records), total: readonly(total), error: readonly(error), pending: readonly(pending),
    loading: computed(() => pending.value && !hasResult.value), refreshing: computed(() => pending.value && hasResult.value),
    retry: load, rememberScroll, restoredScroll,
  }
}
