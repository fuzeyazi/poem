<script setup lang="ts">
import { computed, inject, nextTick, onMounted, onBeforeUnmount, shallowRef, useTemplateRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Menu, Close, Sunny, Moon, SwitchButton } from '@element-plus/icons-vue'
import MaterialNavLinks from './material/MaterialNavLinks.vue'
import { navigationHostKey } from './material/navigationHost'
import { useUserStore } from '@/store/user'
import { getRemindCount } from '@/api/user'
import { useTheme } from '@/composables/useTheme'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const { theme, toggleTheme } = useTheme()
// Keep page-owned navigation mounted while placing its controls before the content bypass target.
const navigationHost = inject(navigationHostKey, null)
const media = window.matchMedia('(max-width: 767px)')
const compact = shallowRef(media.matches)
const drawerOpen = shallowRef(false)
const remindCount = shallowRef(0)
const drawer = useTemplateRef<HTMLDialogElement>('drawer')
const menuButton = useTemplateRef<HTMLButtonElement>('menuButton')
const themeLabel = computed(() => theme.value === 'light' ? '切换深色主题' : '切换浅色主题')
const showTheme = computed(() => !route.path.startsWith('/console'))
let previousFocus: HTMLElement | null = null
let previousOverflow = ''

async function openDrawer() {
  previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : menuButton.value
  previousOverflow = document.body.style.overflow
  drawerOpen.value = true
  await nextTick()
  if (!drawerOpen.value || !drawer.value) return
  drawer.value.showModal()
  document.body.style.overflow = 'hidden'
  drawer.value.querySelector<HTMLButtonElement>('button')?.focus()
}

function closeDrawer() {
  if (!drawerOpen.value) return
  drawer.value?.close()
  drawerOpen.value = false
  document.body.style.overflow = previousOverflow
  if (previousFocus?.isConnected) previousFocus.focus()
}

function onDrawerKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    closeDrawer()
    return
  }
  if (event.key !== 'Tab' || !drawer.value) return
  const controls = Array.from(drawer.value.querySelectorAll<HTMLElement>('a[href], button:not([disabled])'))
  const first = controls[0]
  const last = controls[controls.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last?.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first?.focus()
  }
}

function onBreakpointChange(event: MediaQueryListEvent) {
  closeDrawer()
  compact.value = event.matches
}

function logout() {
  closeDrawer()
  userStore.clearToken()
  router.push('/login')
}

watch(() => route.fullPath, closeDrawer)
onMounted(async () => {
  media.addEventListener('change', onBreakpointChange)
  if (!userStore.token) return
  try {
    const result = await getRemindCount()
    remindCount.value = result?.count || 0
  } catch {
    // Reminder availability should not block navigation.
  }
})
onBeforeUnmount(() => {
  closeDrawer()
  media.removeEventListener('change', onBreakpointChange)
})
</script>

<template>
  <Teleport :to="navigationHost || 'body'" :disabled="!navigationHost" defer>
  <header v-if="compact" class="mobile-appbar">
    <button ref="menuButton" class="md-icon-button" type="button" aria-label="打开导航菜单"
      aria-controls="primary-navigation-drawer" :aria-expanded="drawerOpen" @click="openDrawer">
      <Menu aria-hidden="true" />
    </button>
    <RouterLink to="/poetry" class="brand mobile-brand">古诗文</RouterLink>
    <button v-if="showTheme" class="md-icon-button" type="button" :aria-label="themeLabel"
      :title="themeLabel" @click="toggleTheme">
      <Sunny v-if="theme === 'dark'" aria-hidden="true" /><Moon v-else aria-hidden="true" />
    </button>
  </header>

  <component :is="compact ? 'dialog' : 'aside'" v-if="!compact || drawerOpen" ref="drawer"
    :id="compact ? 'primary-navigation-drawer' : undefined" class="navigation-panel"
    :class="{ 'navigation-drawer': compact }" :aria-modal="compact ? 'true' : undefined"
    :aria-label="compact ? '导航菜单' : undefined" @keydown="onDrawerKeydown" @cancel.prevent="closeDrawer"
    @click.self="compact && closeDrawer()">
    <div class="navigation-heading">
      <button v-if="compact" class="md-icon-button" type="button" aria-label="关闭导航菜单" @click="closeDrawer">
        <Close aria-hidden="true" />
      </button>
      <RouterLink to="/poetry" class="brand"><span class="brand-mark" aria-hidden="true">诵</span><span>古诗文</span></RouterLink>
    </div>
    <p class="navigation-tagline">让诗意走进日常</p>
    <MaterialNavLinks :remind-count="remindCount" @navigate="closeDrawer" />
    <div class="navigation-account">
      <span v-if="userStore.userName" class="account-name">{{ userStore.userName }}</span>
      <button v-if="showTheme && !compact" class="account-button" type="button" :aria-label="themeLabel" @click="toggleTheme">
        <Sunny v-if="theme === 'dark'" aria-hidden="true" /><Moon v-else aria-hidden="true" />
        <span>{{ theme === 'light' ? '深色主题' : '浅色主题' }}</span>
      </button>
      <button v-if="userStore.token" class="account-button" type="button" data-action="logout" @click="logout">
        <SwitchButton aria-hidden="true" /><span>退出登录</span>
      </button>
      <RouterLink v-else class="account-button" to="/login" @click="closeDrawer">登录账户</RouterLink>
    </div>
  </component>
  </Teleport>
</template>

<style scoped>
.navigation-panel { position: fixed; inset: 0 auto 0 0; z-index: 60; width: var(--md-nav-width); display: flex; flex-direction: column; padding: 24px 16px 16px; background: var(--md-surface-container-low); color: var(--md-on-surface); overflow-y: auto; overscroll-behavior: contain; border: 0; }
.navigation-heading { display: flex; align-items: center; min-height: 48px; gap: 8px; }
.brand { display: inline-flex; align-items: center; gap: 12px; min-height: 48px; color: var(--md-on-surface); font-size: 22px; font-weight: 500; letter-spacing: 0; }
.brand-mark { display: grid; place-items: center; width: 40px; height: 40px; background: var(--md-primary-container); color: var(--md-primary); border-radius: 14px; }
.navigation-tagline { color: var(--md-on-surface-variant); font-size: 12px; margin: 4px 0 24px 52px; }
.navigation-account { margin-top: auto; padding-top: 20px; border-top: 1px solid var(--md-outline-variant); }
.account-name { display: block; padding: 8px 16px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 14px; font-weight: 500; }
.account-button { display: flex; align-items: center; gap: 12px; width: 100%; min-height: 48px; padding: 8px 16px; border: 0; border-radius: 24px; font: inherit; font-size: 14px; color: var(--md-on-surface-variant); background: transparent; text-align: left; cursor: pointer; }
.account-button svg { width: 20px; height: 20px; flex-shrink: 0; }
.account-button:hover { background: var(--md-state-hover); }
.account-button:active { background: var(--md-state-pressed); }
.mobile-appbar { position: fixed; inset: 0 0 auto; z-index: 55; height: 64px; display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: var(--md-surface); border-bottom: 1px solid var(--md-outline-variant); }
.mobile-brand { margin-right: auto; font-size: 20px; }
.navigation-drawer { width: min(320px, calc(100vw - 32px)); height: 100dvh; max-height: 100dvh; max-width: none; margin: 0; border-radius: 0 28px 28px 0; box-shadow: var(--md-elevation-3); padding: 12px 16px 20px; }
.navigation-drawer::backdrop { background: var(--md-scrim); }
.navigation-drawer .navigation-tagline { margin-left: 64px; }
@media (prefers-reduced-motion: no-preference) { .navigation-drawer[open] { animation: drawer-enter 200ms ease-out; } }
@keyframes drawer-enter { from { transform: translateX(-24px); opacity: .7; } to { transform: translateX(0); opacity: 1; } }
</style>
