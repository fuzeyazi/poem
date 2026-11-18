<template>
  <div>
    <AppNav />
    <div class="wrap">
      <div class="page-head"><span class="labbtn">反 馈</span><span class="muted">留言建议</span></div>
      <el-form :model="form" label-width="80px" class="inset fb-form" label-position="top" @submit.prevent="submit" :aria-busy="loading">
        <el-form-item label="内容" :error="messageError">
          <el-input v-model="form.message" @input="messageError = ''" type="textarea" :rows="5" placeholder="请写下您的建议或问题..." />
        </el-form-item>
        <p v-if="submitError" class="form-error" role="alert">{{ submitError }}</p>
        <el-form-item><el-button type="primary" native-type="submit" :loading="loading" :disabled="loading">{{ loading ? '提交中…' : '提交' }}</el-button></el-form-item>
      </el-form>

      <div class="fb-list" style="margin-top:28px">
        <div class="muted" style="margin-bottom:10px;letter-spacing:4px">历 史 反 馈</div>
        <div v-for="f in list" :key="f.id" class="fb-item">
          <div class="fb-msg">{{ f.messsage }}</div>
          <div class="fb-reply" v-if="f.reply"><span class="lab">回复：</span>{{ f.reply }}</div>
          <div class="muted" v-else>暂无回复</div>
        </div>
        <div v-if="!list.length" class="hint">暂无反馈记录</div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import AppNav from '@/components/AppNav.vue'
import { addFeedback, getAllFeedBack } from '@/api/feedback'
const form = reactive({ message: '' })
const loading = ref(false)
const list = ref<any[]>([])
const messageError = ref('')
const submitError = ref('')
const submit = async () => {
  if (loading.value) return
  submitError.value = ''
  messageError.value = form.message.trim() ? '' : '请输入反馈内容'
  if (messageError.value) return
  loading.value = true
  try { await addFeedback({ message: form.message.trim() }); ElMessage.success('已提交'); form.message = ''; await loadList() } catch { submitError.value = '提交失败，请稍后重试，内容已保留' } finally { loading.value = false }
}
const loadList = async () => { try { list.value = (await getAllFeedBack()) || [] } catch {} }
onMounted(loadList)
</script>
<style scoped>
.page-head { display: flex; align-items: center; gap: 18px; margin-bottom: 20px; }
.labbtn { font-size: 28px; letter-spacing: normal; color: var(--md-on-surface); border-left: 3px solid var(--md-primary); padding-left: 12px;  border: none;  padding: 0; }
.fb-form { padding: 24px 28px; }
:deep(.el-button--primary) { background: var(--md-primary); color: var(--md-on-primary); border: none; letter-spacing: normal; }
:deep(.el-button--primary:hover) { background: var(--md-primary); }
.fb-item { padding: 20px 24px; background: var(--md-surface-container-lowest); border: 1px solid var(--md-outline-variant); border-radius: 24px; margin-bottom: 12px; box-shadow: var(--shadow-sm); }
.fb-msg { color: var(--md-on-surface); line-height: 1.8; }
.fb-reply { margin-top: 8px; padding-top: 8px; border-top: 1px dashed var(--md-outline-variant); color: var(--md-on-surface); }
.fb-reply .lab { color: var(--md-primary); letter-spacing: normal; }

:deep(.el-button) { min-height: 44px; border-radius: 999px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-input__wrapper) { min-height: 48px; border-radius: 12px; }
:deep(.el-textarea__inner) { border-radius: 12px; font-size: 15px; }
:deep(.el-tabs__item) { min-height: 48px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-dialog) { max-width: calc(100vw - 32px); border-radius: 28px; }
.form-error { font-size: 14px; line-height: 1.5; color: var(--md-error); background: var(--md-error-container); border-radius: 12px; padding: 12px 16px; }

.fb-msg, .fb-reply { overflow-wrap: anywhere; } @media (max-width: 600px) { .fb-form { padding: 20px; } }
</style>
