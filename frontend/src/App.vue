<script setup lang="ts">
import { computed, provide, useTemplateRef } from 'vue'
import { useRoute } from 'vue-router'
import { Sunny, Moon } from '@element-plus/icons-vue'
import SoundscapeWidget from '@/components/soundscape/SoundscapeWidget.vue'
import { setupReviewRemind } from '@/utils/reviewRemind'
import { useTheme } from '@/composables/useTheme'
import { navigationHostKey } from '@/components/material/navigationHost'

const route = useRoute()
const { theme, toggleTheme } = useTheme()
const mainContent = useTemplateRef<HTMLElement>('mainContent')
provide(navigationHostKey, '#app-navigation-host')
const layout = computed(() => {
  if (route.path === '/login') return 'auth'
  if (route.path.startsWith('/console')) return 'console'
  if (route.name === 'not-found') return 'error'
  return 'user'
})
const standaloneTheme = computed(() => layout.value !== 'user')
const themeLabel = computed(() => theme.value === 'light' ? '切换深色主题' : '切换浅色主题')
function focusMainContent() {
  mainContent.value?.focus()
}
// Keep the global review subscription and soundscape alive across routes.
setupReviewRemind()
</script>

<template>
  <div class="app-layout" :class="`app-layout--${layout}`">
    <a class="skip-link" href="#main-content" @click.prevent="focusMainContent">跳到主要内容</a>
    <div id="app-navigation-host" />
    <div id="main-content" ref="mainContent" class="app-shell" tabindex="-1">
      <RouterView />
    </div>
    <button v-if="standaloneTheme" class="md-icon-button standalone-theme" type="button"
      :aria-label="themeLabel" :title="themeLabel" @click="toggleTheme">
      <Sunny v-if="theme === 'dark'" aria-hidden="true" /><Moon v-else aria-hidden="true" />
    </button>
    <SoundscapeWidget />
  </div>
</template>
