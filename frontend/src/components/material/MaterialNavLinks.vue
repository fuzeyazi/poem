<script setup lang="ts">
import { useRoute } from 'vue-router'
import { Reading, User, ChatLineSquare, Calendar, EditPen, MagicStick, Bell, UserFilled, Monitor } from '@element-plus/icons-vue'

defineProps<{ remindCount: number }>()
const emit = defineEmits<{ navigate: [] }>()
const route = useRoute()
const groups = [
  { label: '探索与阅读', items: [
    { path: '/poetry', label: '诗词', icon: Reading },
    { path: '/writers', label: '诗人', icon: User },
    { path: '/rhesis', label: '名句', icon: ChatLineSquare },
    { path: '/review', label: '今日复习', icon: Calendar },
  ] },
  { label: '交流与灵感', items: [
    { path: '/forum', label: '诗坛', icon: EditPen },
    { path: '/ai', label: 'AI 诗友', icon: MagicStick },
    { path: '/notice', label: '公告', icon: Bell },
  ] },
  { label: '我的空间', items: [
    { path: '/center', label: '个人中心', icon: UserFilled },
    { path: '/console', label: '控制台', icon: Monitor },
  ] },
]

function isActive(path: string) {
  return route.path === path || (path === '/poetry' && route.path.startsWith('/poem/')) || (path === '/console' && route.path.startsWith('/console/'))
}
</script>

<template>
  <nav class="primary-navigation" aria-label="主导航">
    <div v-for="group in groups" :key="group.label" class="navigation-group">
      <p class="group-label">{{ group.label }}</p>
      <RouterLink v-for="item in group.items" :key="item.path" :to="item.path"
        class="navigation-link" :class="{ selected: isActive(item.path) }"
        :aria-current="isActive(item.path) ? 'page' : undefined" @click="emit('navigate')">
        <component :is="item.icon" aria-hidden="true" /><span>{{ item.label }}</span>
        <span v-if="item.path === '/review' && remindCount > 0" class="reminder-badge"
          :aria-label="`${remindCount} 条复习提醒`">{{ remindCount > 99 ? '99+' : remindCount }}</span>
      </RouterLink>
    </div>
  </nav>
</template>

<style scoped>
.primary-navigation { padding-bottom: 24px; }
.navigation-group + .navigation-group { margin-top: 16px; }
.group-label { margin: 0 16px 8px; font-size: 12px; color: var(--md-on-surface-variant); font-weight: 500; }
.navigation-link { display: flex; align-items: center; gap: 12px; min-height: 48px; padding: 10px 16px; border-radius: 28px; color: var(--md-on-surface-variant); font-size: 14px; font-weight: 500; transition: background 120ms, color 120ms; }
.navigation-link svg { width: 22px; height: 22px; flex-shrink: 0; }
.navigation-link:hover { background: var(--md-state-hover); }
.navigation-link:active { background: var(--md-state-pressed); }
.navigation-link.selected { color: var(--md-on-primary-container); background: var(--md-primary-container); }
.navigation-link.selected:hover { background: color-mix(in srgb, var(--md-primary-container) 92%, var(--md-on-primary-container)); }
.navigation-link.selected:active { background: color-mix(in srgb, var(--md-primary-container) 88%, var(--md-on-primary-container)); }
.reminder-badge { min-width: 24px; padding: 0 6px; margin-left: auto; border-radius: 12px; color: var(--md-on-error); background: var(--md-error); font-size: 11px; line-height: 22px; text-align: center; }
</style>
