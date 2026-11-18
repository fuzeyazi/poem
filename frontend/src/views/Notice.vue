<template>
  <div>
    <AppNav />
    <div class="wrap">
      <div class="page-head"><span class="labbtn">公 告</span><span class="muted">站点通告</span></div>
      <div v-loading="loading" class="notice-list">
        <el-empty v-if="!loading && failed" description="公告暂时取不到，稍后再来看看" />
        <el-empty v-else-if="!loading && !list.length" description="暂无公告" />
        <div v-for="n in list" :key="n.id" class="notice-item inset">
          <div class="n-title">{{ n.name }}</div>
          <div class="n-content">{{ n.contents }}</div>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import AppNav from '@/components/AppNav.vue'
import { getNoticeList } from '@/api/notice'
const list = ref<any[]>([])
const loading = ref(false)
const failed = ref(false)
onMounted(async () => {
  loading.value = true
  try {
    const p: any = await getNoticeList()
    list.value = p?.records || p || []
  } catch { failed.value = true } finally { loading.value = false }
})
</script>
<style scoped>
.page-head { display: flex; align-items: center; gap: 18px; margin-bottom: 20px; }
.labbtn { font-size: 28px; letter-spacing: normal; color: var(--md-on-surface); border-left: 3px solid var(--md-primary); padding-left: 12px;  border: none;  padding: 0; }
.notice-item { padding: 22px 26px; margin-bottom: 14px; }
.n-title { font-size: 18px; letter-spacing: normal; color: var(--md-on-surface); margin-bottom: 10px; }
.n-content { color: var(--md-on-surface); line-height: 2; white-space: pre-wrap; }

:deep(.el-button) { min-height: 44px; border-radius: 999px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-input__wrapper) { min-height: 48px; border-radius: 12px; }
:deep(.el-textarea__inner) { border-radius: 12px; font-size: 15px; }
:deep(.el-tabs__item) { min-height: 48px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-dialog) { max-width: calc(100vw - 32px); border-radius: 28px; }
.form-error { font-size: 14px; line-height: 1.5; color: var(--md-error); background: var(--md-error-container); border-radius: 12px; padding: 12px 16px; }

.n-content { overflow-wrap: anywhere; }
</style>