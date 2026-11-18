<template>
  <div class="crud-container">
    <div class="crud-toolbar">
      <div class="crud-hint" v-if="hint">
        <svg class="hint-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="16" x2="12" y2="12" />
          <line x1="12" y1="8" x2="12.01" y2="8" />
        </svg>
        <span>{{ hint }}</span>
      </div>
      <div v-else></div>
      <div class="crud-actions">
        <el-button v-if="add" size="small" type="primary" class="action-btn-primary" @click="openAdd">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 4px">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          新增条目
        </el-button>
      </div>
    </div>

    <div class="table-frame">
      <el-table :data="rows" v-loading="loading" size="small" class="craft-table">
        <el-table-column v-for="c in columns" :key="c.prop" :prop="c.prop" :label="c.label"
          :width="c.width" :show-overflow-tooltip="!!c.tooltip">
          <template #default="{ row }">
            <span v-if="c.prop === 'id'" class="id-pill">#{{ row[idKey] }}</span>
            <span v-else-if="c.formatter">{{ c.formatter(row) }}</span>
            <span v-else>{{ row[c.prop] }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" :width="actionWidth" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button v-if="update" link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
              <el-button v-if="remove" link type="danger" size="small" @click="onDelete(row)">删除</el-button>
              <slot name="row" :row="row" />
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="crud-pager">
      <span class="total-caption">共 {{ total }} 条记录</span>
      <el-pagination layout="prev, pager, next" :total="total" :page-size="pageSize"
        :current-page="page" @current-change="onPage" background size="small" />
    </div>

    <el-dialog v-model="dlg" :title="editing ? '编辑记录' : '新增记录'" width="min(560px, calc(100vw - 32px))" align-center class="craft-dialog">
      <el-form label-position="top" class="craft-form" @submit.prevent="save" :aria-busy="saving">
        <el-form-item v-for="f in formFields" :key="f.prop" :label="f.label">
          <el-input v-if="f.type === 'textarea'" v-model="form[f.prop]" type="textarea" :rows="5" placeholder="请输入内容..." />
          <el-input v-else v-model="form[f.prop]" placeholder="请输入..." />
        </el-form-item>
      </el-form>
      <p v-if="saveError" class="form-error" role="alert">{{ saveError }}</p>
      <template #footer>
        <div class="dialog-footer">
          <el-button size="small" :disabled="saving" @click="dlg = false">取消</el-button>
          <el-button size="small" type="primary" :loading="saving" :disabled="saving" @click="save">保存提交</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const props = defineProps<{
  hint?: string
  columns: { prop: string; label: string; width?: number | string; tooltip?: boolean; formatter?: any }[]
  formFields: { prop: string; label: string; type?: 'textarea' }[]
  list: (pageNum: number, pageSize: number) => Promise<any>
  add?: (form: any) => Promise<any>
  update?: (form: any) => Promise<any>
  remove?: (ids: number[]) => Promise<any>
  idKey?: string
  actionWidth?: number | string
}>()

const rows = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)
const dlg = ref(false)
const editing = ref(false)
const saving = ref(false)
const saveError = ref('')
const form = ref<any>({})
const idKey = props.idKey || 'id'

const load = async () => {
  loading.value = true
  try {
    const d = await props.list(page.value, pageSize)
    rows.value = d?.records ?? d?.list ?? []
    total.value = Number(d?.total ?? rows.value.length)
  } catch (e: any) {
    rows.value = []; total.value = 0
  } finally { loading.value = false }
}
const onPage = (p: number) => { page.value = p; load() }

const openAdd = () => { editing.value = false; form.value = {}; saveError.value = ''; dlg.value = true }
const openEdit = (row: any) => {
  editing.value = true
  saveError.value = ''
  form.value = { ...row }
  dlg.value = true
}
const save = async () => {
  if (saving.value) return
  const action = editing.value ? props.update : props.add
  if (!action) return
  saveError.value = ''
  saving.value = true
  try {
    await action({ ...form.value })
    ElMessage.success('已保存')
    dlg.value = false
    load()
  } catch (e: any) {
    saveError.value = '保存失败，请重试，编辑内容已保留'
  } finally { saving.value = false }
}
const onDelete = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确认删除「${row.title || row.name || row.username || row.id}」？`, '删除确认', { type: 'warning' })
  } catch { return }
  try {
    await props.remove?.([row[idKey]])
    ElMessage.success('已删除')
    load()
  } catch (e: any) {
    // 请求层统一显示删除失败通知。
  }
}
const reload = () => { page.value = 1; load() }
defineExpose({ reload, load })
onMounted(load)
</script>

<style scoped>
.crud-container {
  display: flex;
  flex-direction: column;
}

.crud-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  gap: 12px;
}

.crud-hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--md-on-surface-variant);
  background: var(--md-surface-container);
  border: 1px solid var(--md-outline-variant);
  padding: 4px 10px;
  border-radius: 12px;
}

.hint-icon {
  color: var(--md-primary);
  flex-shrink: 0;
}

.action-btn-primary {
  display: inline-flex;
  align-items: center;
  font-size: 13px;
  letter-spacing: normal;
}

.table-frame {
  border: 1px solid var(--md-outline-variant);
  border-radius: 16px;
  overflow: auto;
  background: var(--md-surface-container-low);
 max-width: 100%; }

.craft-table {
  width: 100%;
}

:deep(.craft-table .el-table__header-wrapper th) {
  background: var(--md-surface-container) !important;
  color: var(--md-on-surface-variant) !important;
  font-weight: 500;
  font-size: 13px;
  letter-spacing: normal;
  border-bottom: 1px solid var(--md-outline-variant);
  padding: 8px 0;
}

:deep(.craft-table .el-table__row) {
  background: transparent !important;
  color: var(--md-on-surface);
  font-size: 13px;
  transition: background 0.15s ease;
}

:deep(.craft-table .el-table__row:hover > td) {
  background: var(--md-surface-container) !important;
}

:deep(.craft-table td) {
  border-bottom: 1px solid var(--md-outline-variant);
  padding: 8px 0;
}

.id-pill {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  color: var(--md-on-surface-variant);
  background: var(--md-surface-container);
  padding: 2px 6px;
  border-radius: 12px;
  border: 1px solid var(--md-outline-variant);
}

.row-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.crud-pager {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 14px;
  padding: 4px 2px;
}

.total-caption {
  font-size: 13px;
  color: var(--md-on-surface-variant);
  font-variant-numeric: tabular-nums;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

:deep(.el-button) { min-height: 44px; border-radius: 999px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-input__wrapper) { min-height: 48px; border-radius: 12px; }
:deep(.el-textarea__inner) { border-radius: 12px; font-size: 15px; }
:deep(.el-tabs__item) { min-height: 48px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-dialog) { max-width: calc(100vw - 32px); border-radius: 28px; }
.form-error { font-size: 14px; line-height: 1.5; color: var(--md-error); background: var(--md-error-container); border-radius: 12px; padding: 12px 16px; }

button, .cs-nav-btn, .nav-content-btn, .nav-console-btn, .unauth-btn { min-height: 44px; border-radius: 999px; } .crud-container, .tab-panel, .panel-section, .ca-container, .cs-container { min-width: 0; max-width: 100%; } .craft-input { min-height: 48px; max-width: 100%; border-radius: 12px; } .crud-pager, .dialog-actions, .dialog-footer, .craft-toolbar, .toolbar-left, .toolbar-right { gap: 12px; flex-wrap: wrap; }
</style>
