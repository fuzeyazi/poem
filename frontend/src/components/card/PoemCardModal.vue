<template>
  <el-dialog
    v-model="dialogVisible"
    title="定格诗意 · 雅致卡片生成器"
    width="min(920px, calc(100vw - 32px))"
    class="poem-card-dialog"
    destroy-on-close
    align-center
  >
    <div class="modal-layout">
      <!-- 左侧：卡片实时所见即所得预览区 -->
      <div class="preview-panel">
        <div class="preview-scroll-container">
          <PoemCardRenderer
            ref="rendererRef"
            :poem="poem"
            :theme="theme"
            :remove-punctuation="removePunctuation"
            :traditional="traditional"
            :user-seal-text="userSealText"
            :user-seal-shape="userSealShape"
            :user-seal-carving="userSealCarving"
            :show-author-seal="showAuthorSeal"
            :show-user-seal="showUserSeal"
          />
        </div>
        <div class="preview-hint">
          <span>* 导出时将自动以 300DPI 超高清分辨率渲染纯净 PNG</span>
        </div>
      </div>

      <!-- 右侧：古典排版与篆刻控制台 -->
      <div class="controls-panel">
        <!-- 1. 主题选择 -->
        <div class="control-section">
          <div class="section-title">卡片笺纸底韵</div>
          <div class="theme-options">
            <button type="button" class="theme-chip"
              :class="{ active: theme === 'xuan' }"
              :aria-pressed="theme === 'xuan'"
              @click="theme = 'xuan'"
            >
              <span class="chip-color xuan" />
              <span class="chip-info">
                <span class="chip-name">澄素宣纸</span>
                <span class="chip-desc">传世墨韵，天然微纤维纸感</span>
              </span>
            </button>

            <button type="button" class="theme-chip"
              :class="{ active: theme === 'dark' }"
              :aria-pressed="theme === 'dark'"
              @click="theme = 'dark'"
            >
              <span class="chip-color dark" />
              <span class="chip-info">
                <span class="chip-name">墨夜泥金</span>
                <span class="chip-desc">OpenDesign 墨夜黑金，沉稳幽深</span>
              </span>
            </button>

            <button type="button" class="theme-chip"
              :class="{ active: theme === 'grid' }"
              :aria-pressed="theme === 'grid'"
              @click="theme = 'grid'"
            >
              <span class="chip-color grid" />
              <span class="chip-info">
                <span class="chip-name">朱丝阑格</span>
                <span class="chip-desc">唐宋经卷细朱丝格，文人手泽</span>
              </span>
            </button>
          </div>
        </div>

        <!-- 2. 古法排版与标点 -->
        <div class="control-section">
          <div class="section-title">文字与古法句读</div>
          <div class="toggle-row">
            <span class="toggle-label">字体版式</span>
            <el-radio-group v-model="traditional" size="small">
              <el-radio-button :value="true">繁体正字</el-radio-button>
              <el-radio-button :value="false">简体中文</el-radio-button>
            </el-radio-group>
          </div>

          <div class="toggle-row">
            <span class="toggle-label">句读标点</span>
            <el-radio-group v-model="removePunctuation" size="small">
              <el-radio-button :value="true">古法无句读</el-radio-button>
              <el-radio-button :value="false">保留标点</el-radio-button>
            </el-radio-group>
          </div>
        </div>

        <!-- 3. 个性化金石印章 -->
        <div class="control-section">
          <div class="section-title">落款雅印篆刻</div>

          <div class="form-row">
            <span class="form-label">自定义印文</span>
            <div class="input-with-tip">
              <el-input
                v-model="userSealText"
                maxlength="4"
                placeholder="1~4字，如 雅赏、太白"
                clearable
                size="small"
                style="width: 190px"
              />
              <span class="tip-text">{{ userSealText.length }}/4 字</span>
            </div>
          </div>

          <div class="toggle-row">
            <span class="toggle-label">印章形制</span>
            <el-radio-group v-model="userSealShape" size="small">
              <el-radio-button value="square">方印</el-radio-button>
              <el-radio-button value="oval">圆印</el-radio-button>
            </el-radio-group>
          </div>

          <div class="toggle-row">
            <span class="toggle-label">篆刻刻法</span>
            <el-radio-group v-model="userSealCarving" size="small">
              <el-radio-button value="yin">白文 (阴刻)</el-radio-button>
              <el-radio-button value="yang">朱文 (阳刻)</el-radio-button>
            </el-radio-group>
          </div>

          <div class="toggle-row checkbox-row">
            <el-checkbox v-model="showAuthorSeal">作者本名印</el-checkbox>
            <el-checkbox v-model="showUserSeal">藏书品鉴印</el-checkbox>
          </div>
        </div>

        <!-- 4. 导出操作区 -->
        <div class="action-footer">
          <el-button
            type="primary"
            class="export-btn"
            :loading="exporting"
            @click="handleExport"
          >
            <span v-if="!exporting">🔖 下载高清卡片 (PNG)</span>
            <span v-else>正在雕版渲染高清图...</span>
          </el-button>
          <el-button
            class="copy-btn"
            :disabled="exporting"
            @click="handleCopy"
          >
            📋 复制图片
          </el-button>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import PoemCardRenderer from './PoemCardRenderer.vue'
import type { PoemCardData } from './PoemCardRenderer.vue'
import { exportCardImage, formatCardFilename, getCardBlob } from '@/utils/cardExporter'
import { useUserStore } from '@/store/user'

const props = defineProps<{
  visible: boolean
  poem: PoemCardData
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
}>()

const userStore = useUserStore()
const rendererRef = ref<InstanceType<typeof PoemCardRenderer> | null>(null)

// 响应式对话框显隐绑定
const dialogVisible = computed({
  get: () => props.visible,
  set: (val: boolean) => emit('update:visible', val)
})

// 卡片参数状态
const theme = ref<'xuan' | 'dark' | 'grid'>('xuan')
const traditional = ref(true)
const removePunctuation = ref(true)
const userSealText = ref('雅赏')
const userSealShape = ref<'square' | 'oval'>('square')
const userSealCarving = ref<'yin' | 'yang'>('yin')
const showAuthorSeal = ref(true)
const showUserSeal = ref(true)
const exporting = ref(false)

// 每次打开时，若有当前登录用户昵称，则默认取用户前两字
watch(
  () => props.visible,
  (val) => {
    if (val && userStore.userName) {
      const name = userStore.userName.trim().slice(0, 4)
      if (name) {
        userSealText.value = name
      }
    }
  }
)

/**
 * 触发高清图片导出与下载
 */
const handleExport = async () => {
  const el = rendererRef.value?.cardRoot || (rendererRef.value as any)?.$el
  if (!el) {
    ElMessage.error('卡片渲染节点尚未准备就绪，请稍候')
    return
  }

  exporting.value = true
  try {
    const filename = formatCardFilename(props.poem.writer, props.poem.title)
    await exportCardImage(el, filename, { pixelRatio: 3 })
    ElMessage.success('高清诗词卡片已生成并开始下载')
  } catch (err: any) {
    console.error('导出卡片失败:', err)
    ElMessage.error(`导出失败：${err?.message || '请稍后重试'}`)
  } finally {
    exporting.value = false
  }
}

/**
 * 复制图片到剪贴板
 */
const handleCopy = async () => {
  const el = rendererRef.value?.cardRoot || (rendererRef.value as any)?.$el
  if (!el) return

  if (typeof navigator === 'undefined' || !navigator.clipboard || !window.ClipboardItem) {
    ElMessage.warning('当前浏览器环境不支持直接复制图片，请使用“下载高清卡片”保存')
    return
  }

  exporting.value = true
  try {
    const blob = await getCardBlob(el, { pixelRatio: 2 })
    if (blob) {
      await navigator.clipboard.write([
        new window.ClipboardItem({ 'image/png': blob })
      ])
      ElMessage.success('已将高清卡片复制到剪贴板')
    }
  } catch (err: any) {
    ElMessage.warning('复制到剪贴板失败，请直接点击下载按钮')
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped>
:deep(.poem-card-dialog) {
  background: var(--md-surface-container-low);
  border: 1px solid var(--md-outline-variant);
  border-radius: 28px;
}

:deep(.poem-card-dialog .el-dialog__header) {
  border-bottom: 1px solid var(--md-outline-variant);
  padding: 16px 24px;
  margin-right: 0;
}

:deep(.poem-card-dialog .el-dialog__title) {
  font-family: var(--f-sans);
  font-weight: 500;
  font-size: 17px;
  letter-spacing: normal;
  color: var(--md-on-surface);
}

:deep(.poem-card-dialog .el-dialog__body) {
  padding: 24px;
}

.modal-layout {
  display: flex;
  gap: 28px;
  align-items: stretch;
}

/* 左侧卡片预览区 */
.preview-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: var(--md-surface-container-high);
  border: 1px solid var(--md-outline-variant);
  border-radius: 24px;
  padding: 24px 16px 16px;
}

.preview-scroll-container {
  width: 100%;
  max-height: 620px;
  overflow-y: auto;
  overflow-x: auto;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 8px 4px;
}

.preview-hint {
  margin-top: 14px;
  font-size: 13px;
  color: var(--md-on-surface-variant);
  letter-spacing: normal;
}

/* 右侧控制区 */
.controls-panel {
  width: 320px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.control-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 16px;
  border-bottom: 1px dashed var(--md-outline-variant);
}

.section-title {
  font-family: var(--f-sans);
  font-size: 13px;
  font-weight: 500;
  color: var(--md-on-surface);
  letter-spacing: normal;
}

/* 主题选择 Chip */
.theme-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.theme-chip {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-radius: 16px;
  border: 1px solid var(--md-outline-variant);
  background: var(--md-surface-container);
  cursor: pointer;
  transition: all 0.2s;
 min-height: 64px;  text-align: left;  font-family: var(--f-sans); }

.theme-chip:hover {
  background: var(--md-surface-container);
  border-color: var(--md-outline-variant);
}

.theme-chip.active {
  background: var(--md-primary-container);
  color: var(--md-on-primary-container);
  border-color: var(--md-primary);
}

.chip-color {
  width: 24px;
  height: 24px;
  border-radius: 12px;
  flex-shrink: 0;
  border: 1px solid var(--md-outline-variant);
}

.chip-color.xuan {
  background-color: #f7f4ec;
  border-color: #c5b497;
}

.chip-color.dark {
;
  background-color: #111622;
  border-color: #d4af37;
}

.chip-color.grid {
  background-color: #f9f6ed;
  border: 1px solid #c0392b;
}

.chip-info {
  display: flex;
  flex-direction: column;
}

.chip-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--md-on-surface);
  letter-spacing: normal;
}

.chip-desc {
  font-size: 13px;
  color: var(--md-on-surface-variant);
}

/* 开关行与表单项 */
.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.toggle-label, .form-label {
  font-size: 13px;
  color: var(--md-on-surface-variant);
  letter-spacing: normal;
}

.form-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.input-with-tip {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tip-text {
  font-size: 13px;
  color: var(--md-on-surface-variant);
}

.checkbox-row {
  justify-content: flex-start;
  gap: 20px;
  margin-top: 4px;
}

:deep(.el-radio-button__inner) {
  background: var(--md-surface-container);
  color: var(--md-on-surface);
  border-color: var(--md-outline-variant);
}

:deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: var(--md-primary);
  border-color: var(--md-primary);
  color: var(--md-on-primary);
  font-weight: 500;
}

:deep(.el-input__wrapper) {
  background-color: var(--md-surface-container-high);
  box-shadow: var(--shadow-sm);
}

:deep(.el-input__inner) {
  color: var(--md-on-surface);
  letter-spacing: normal;
}

/* 操作底部 */
.action-footer {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 8px;
}

.export-btn {
  height: 48px;
  background: var(--md-primary);
  border-color: var(--md-on-primary);
  color: var(--md-on-primary);
  font-weight: 500;
  letter-spacing: normal;
  font-size: 14px;
  transition: all 0.2s;
}

.export-btn:hover {
  background: var(--md-primary);
  border-color: var(--md-on-primary);
  color: var(--md-on-primary);
}

.copy-btn {
  height: 48px;
  background: transparent;
  border: 1px solid var(--md-outline-variant);
  color: var(--md-on-surface);
  letter-spacing: normal;
  font-size: 13px;
 border-radius: 999px; }

.copy-btn:hover {
  border-color: var(--md-primary);
  color: var(--md-on-surface);
  background: var(--md-primary-container);
}

@media (max-width: 860px) {
  .modal-layout {
    flex-direction: column;
  }
  .controls-panel {
    width: 100%;
  }
}

:deep(.el-button) { min-height: 44px; border-radius: 999px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-input__wrapper) { min-height: 48px; border-radius: 12px; }
:deep(.el-textarea__inner) { border-radius: 12px; font-size: 15px; }
:deep(.el-tabs__item) { min-height: 48px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-dialog) { max-width: calc(100vw - 32px); border-radius: 28px; }
.form-error { font-size: 14px; line-height: 1.5; color: var(--md-error); background: var(--md-error-container); border-radius: 12px; padding: 12px 16px; }

.theme-chip.active .chip-name, .theme-chip.active .chip-desc { color: var(--md-on-primary-container); } .toggle-row, .form-row, .checkbox-row { flex-wrap: wrap; gap: 12px; } :deep(.el-radio-button__inner) { min-height: 44px; display: inline-flex; align-items: center; } .preview-scroll-container { justify-content: flex-start; } @media (max-width: 600px) { .preview-panel { padding: 16px 8px; } :deep(.poem-card-dialog .el-dialog__body) { padding: 16px; } .modal-layout { gap: 20px; } }
</style>
