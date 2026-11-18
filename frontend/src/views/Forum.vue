<template>
  <div>
    <AppNav />
    <div class="wrap">
      <div class="page-head">
        <span class="labbtn">诗 坛</span>
        <el-button class="post-btn" @click="showPost=true">＋ 发 帖</el-button>
      </div>

      <div class="cat-tabs">
        <button v-for="c in cats" :key="c.v" type="button" class="cat" :class="{ on: cat === c.v }" :aria-pressed="cat === c.v" @click="onCat(c.v)">{{ c.l }}</button>
      </div>

      <div class="searchbox">
        <input v-model="kw" aria-label="搜索帖子内容" placeholder="搜索帖子内容" @keyup.enter="onSearch" />
        <button class="btn" @click="onSearch">检 索</button>
      </div>

      <div v-loading="loading" class="blog-list">
        <div v-for="(b, i) in list" :key="b.id" v-reveal="(i % 5) * 60" class="blog-card" tabindex="0" role="button" @keydown.enter="openBlog(b.id)" @keydown.space.prevent="openBlog(b.id)" @click="openBlog(b.id)">
          <div v-if="b.images" class="cover"><img :src="b.images" @error="onErr" /></div>
          <div class="bc-body">
            <div class="bc-title">{{ b.title }}</div>
            <div class="bc-meta muted">
              <img v-if="b.touxiang" :src="b.touxiang" class="bc-avatar" @error="onErr" />
              {{ b.username }} · {{ b.type || '杂谈' }} · 赞 {{ b.liked || 0 }} · 评 {{ b.conmments || 0 }}
            </div>
            <div class="bc-content ell2">{{ strip(b.content) }}</div>
          </div>
        </div>
        <div v-if="!loading && !list.length" class="empty-state muted">暂无帖子</div>
      </div>

      <div v-if="total > pageSize" class="pagination-bar">
        <el-pagination v-model:current-page="pageNum" :page-size="pageSize" :total="total" layout="prev, pager, next" @current-change="onPage" />
      </div>

      <el-dialog v-model="showPost" title="发帖" width="min(560px, calc(100vw - 32px))">
        <el-form :model="postForm" label-position="top" @submit.prevent="onPost" :aria-busy="postPending">
          <el-form-item label="标题" :error="postErrors.title"><el-input v-model="postForm.title" @input="postErrors.title = ''" /></el-form-item>
          <el-form-item label="类型">
            <el-select v-model="postForm.type" placeholder="选择类型">
              <el-option v-for="c in cats" :key="c.v" :value="c.l" :label="c.l" />
            </el-select>
          </el-form-item>
          <el-form-item label="内容" :error="postErrors.content"><el-input v-model="postForm.content" @input="postErrors.content = ''" type="textarea" :rows="6" /></el-form-item>
        </el-form>
        <p v-if="postError" class="form-error" role="alert">{{ postError }}</p>
        <template #footer><el-button @click="showPost=false" :disabled="postPending">取消</el-button><el-button type="primary" @click="onPost" :loading="postPending" :disabled="postPending">{{ postPending ? '发布中…' : '发布' }}</el-button></template>
      </el-dialog>

      <el-dialog v-model="showBlog" :title="blog?.title" width="min(680px, calc(100vw - 32px))" top="6vh">
        <div v-if="blog" class="blog-detail">
          <div class="blog-meta muted">
            <img v-if="blog.touxiang" :src="blog.touxiang" class="bc-avatar" @error="onErr" />
            {{ blog.username }} · {{ blog.createTime }} · {{ blog.type }}
          </div>
          <div v-if="blog.images" class="blog-cover"><img :src="blog.images" @error="onErr" /></div>
          <div class="blog-content">{{ blog.content }}</div>
          <div v-if="blog.poemWord" class="blog-poem">「{{ blog.poemWord }}」</div>
          <div class="blog-actions">
            <el-button size="small" @click="likeBlog(blog.id)">赞 ({{ blog.liked || 0 }})</el-button>
          </div>
          <div class="cm-lab">评论 ({{ comments.length }})</div>
          <div v-for="c in comments" :key="c.id" class="cm-item">
            <img v-if="c.touxiang" :src="c.touxiang" class="cm-avatar" @error="onErr" />
            <div class="cm-body">
              <div class="cm-user">{{ c.name || '匿名' }} <span class="cm-time muted">{{ c.createTiem }}</span></div>
              <div class="cm-text">{{ c.context }}</div>
              <div class="cm-ops">
                <button class="op" type="button" @click="likeComment(c)">赞 {{ c.liked || 0 }}</button>
                <button class="op" type="button" @click="startReply(c)">回复</button>
                <span v-if="(c.conment || 0) > 0" class="op muted">{{ c.conment }} 条回复</span>
              </div>
              <div v-for="child in c.children" :key="child.id" class="cm-child">
                <img v-if="child.touxiang" :src="child.touxiang" class="cm-avatar sm" @error="onErr" />
                <div class="cm-body">
                  <div class="cm-user">
                    {{ child.name || '匿名' }}
                    <span v-if="child.replyToUserName" class="muted">回复 @{{ child.replyToUserName }}</span>
                    <span class="cm-time muted">{{ child.createTiem }}</span>
                  </div>
                  <div class="cm-text">{{ child.context }}</div>
                  <div class="cm-ops"><button class="op" type="button" @click="startReply(child)">回复</button></div>
                </div>
              </div>
            </div>
          </div>
          <div v-if="!comments.length" class="hint">尚无评论</div>
          <div v-if="commentsError" class="form-error" role="alert">
            <span>{{ commentsError }}</span>
            <el-button size="small" :loading="commentsPending" :disabled="commentsPending" @click="refreshComments(blog.id)">重试加载评论</el-button>
          </div>
          <div class="cm-input">
            <div v-if="replyTo" class="replying">
              回复 @{{ replyTo.name || '匿名' }}
              <button class="cancel" type="button" aria-label="取消回复" @click="replyTo = null">✕</button>
            </div>
            <el-form @submit.prevent="postCm" :aria-busy="cmPending">
              <el-form-item label="评论" :error="cmFieldError">
                <div class="cm-input-row">
                  <el-input v-model="cmText" @input="cmFieldError = ''" :placeholder="replyTo ? '回复 @' + (replyTo.name || '匿名') + '...' : '写评论...'" />
                  <el-button type="primary" native-type="submit" :loading="cmPending" :disabled="cmPending">{{ cmPending ? '发表中…' : '发表' }}</el-button>
                </div>
              </el-form-item>
            </el-form>
            <p v-if="cmError" class="form-error" role="alert">{{ cmError }}</p>
          </div>
        </div>
      </el-dialog>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, shallowRef, reactive, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import AppNav from '@/components/AppNav.vue'
import { selectTiez, searchForum, postBlog, selectXiangxi, dianzan, selectComments, postForumComment, commentDianzan } from '@/api/forum'
import { useUserStore } from '@/store/user'
import { Client, type IMessage } from '@stomp/stompjs'
import type { ForumCommentVo } from '@/api/types'

const userStore = useUserStore()
const list = ref<any[]>([])
const kw = ref('')
const loading = ref(false)
const cat = ref(1)
const pageNum = ref(1)
const pageSize = ref(4)
const total = ref(0)
const cats = [
  { v: 1, l: '诗词创作' },
  { v: 2, l: '诗词赏析' },
  { v: 3, l: '诗词学习' },
  { v: 4, l: '诗词活动' },
  { v: 5, l: '诗词资源' },
  { v: 6, l: '诗词杂谈' },
]
const strip = (s?: string) => (s || '').replace(/<[^>]+>/g, '').replace(/^#+\s*/gm, '').replace(/\n+/g, ' ').trim()
const onErr = (e: Event) => { (e.target as HTMLImageElement).style.display = 'none' }

const load = async () => {
  loading.value = true
  try {
    const p: any = await selectTiez(cat.value, pageNum.value, pageSize.value)
    list.value = p?.records || []
    total.value = p?.total || 0
  } catch { list.value = []; total.value = 0 }
  finally { loading.value = false }
}
const onCat = (c: number) => { cat.value = c; pageNum.value = 1; kw.value = ''; load() }
const onPage = (p: number) => { pageNum.value = p; load() }
const onSearch = async () => {
  if (!kw.value.trim()) return
  loading.value = true
  try { list.value = (await searchForum(kw.value.trim())) || []; total.value = list.value.length }
  finally { loading.value = false }
}

const showPost = ref(false)
const postForm = reactive({ title: '', type: '诗词创作', content: '' })
const postPending = ref(false)
const postError = ref('')
const postErrors = reactive({ title: '', content: '' })
const onPost = async () => {
  if (postPending.value) return
  postError.value = ''
  postErrors.title = postForm.title.trim() ? '' : '请输入标题'
  postErrors.content = postForm.content.trim() ? '' : '请输入内容'
  if (postErrors.title || postErrors.content) return
  postPending.value = true
  try {
    await postBlog({ ...postForm, title: postForm.title.trim(), content: postForm.content.trim() })
    ElMessage.success('已发布')
    showPost.value = false
    postForm.title = ''; postForm.content = ''
    await load()
  } catch { postError.value = '发布失败，请重试，草稿已保留' } finally { postPending.value = false }
}

const showBlog = ref(false)
const blog = ref<any>(null)
const comments = ref<ForumCommentVo[]>([])
const cmText = ref('')
// 被回复的评论（任意层级）；parentId 由后端归一到根评论并记录 replyToUserName
const replyTo = ref<ForumCommentVo | null>(null)
const startReply = (c: ForumCommentVo) => { replyTo.value = c }
const openBlog = async (id: number) => {
  showBlog.value = true; blog.value = null; comments.value = []; cmText.value = ''; replyTo.value = null
  commentsError.value = ''; cmError.value = ''
  try { blog.value = await selectXiangxi(id) } catch {}
  try { comments.value = (await selectComments(id)) || [] } catch {}
}
const likeBlog = async (id: number) => {
  try {
    await dianzan(id)
    // 后端是 toggle 语义（已赞再点=取消），本地 +1 会漂移——以回查详情为准
    if (blog.value) blog.value = await selectXiangxi(id)
    ElMessage.success('已更新')
  }
  catch {}
}
const likeComment = async (c: ForumCommentVo) => {
  if (!blog.value) return
  try {
    const msg = await commentDianzan(c.id!)
    ElMessage.success(String(msg || '已更新'))
    comments.value = (await selectComments(blog.value.id)) || []
  } catch {}
}
const cmPending = ref(false)
const cmError = ref('')
const cmFieldError = ref('')
const commentsError = shallowRef('')
const commentsPending = shallowRef(false)
const refreshComments = async (blogId: number, afterPublish = false) => {
  if (commentsPending.value || blog.value?.id !== blogId) return
  commentsPending.value = true
  commentsError.value = ''
  try {
    const records = await selectComments(blogId)
    if (blog.value?.id === blogId) comments.value = records || []
  } catch {
    if (blog.value?.id === blogId) {
      commentsError.value = afterPublish ? '评论已提交，列表刷新失败，请重试加载' : '评论加载失败，请重试加载'
    }
  } finally { commentsPending.value = false }
}
const postCm = async () => {
  if (cmPending.value || !blog.value) return
  cmError.value = ''
  cmFieldError.value = cmText.value.trim() ? '' : '请输入评论内容'
  if (cmFieldError.value) return
  const blogId = blog.value.id
  cmPending.value = true
  try {
    await postForumComment({
      blogId,
      context: cmText.value.trim(),
      parentId: replyTo.value?.id,
      tagerrName: userStore.userName,
    })
    ElMessage.success('评论成功')
    if (blog.value?.id === blogId) {
      cmText.value = ''
      replyTo.value = null
      await refreshComments(blogId, true)
    }
  } catch {
    if (blog.value?.id === blogId) cmError.value = '评论失败，请重试，内容已保留'
  } finally { cmPending.value = false }
}

// 发帖实时推送：订阅 /topic/newpost（后端 RabbitMQ→STOMP 广播），有新帖则提示并刷新第一页
let stomp: Client | null = null
const connectNewpost = () => {
  try {
    stomp = new Client({
      brokerURL: `ws://${location.host}/ws/websocket`,
      reconnectDelay: 6000,
      onConnect: () => {
        stomp?.subscribe('/topic/newpost', (msg: IMessage) => {
          try {
            const d = JSON.parse(msg.body)
            ElMessage.success(`新帖发布：《${d.title ?? ''}》`)
            if (pageNum.value === 1 && !kw.value.trim()) load()
          } catch { /* 忽略坏帧 */ }
        })
      },
    })
    stomp.activate()
  } catch { /* 推送不可用不影响主流程 */ }
}
onMounted(() => { load(); connectNewpost() })
onBeforeUnmount(() => { stomp?.deactivate(); stomp = null })
</script>

<style scoped>
.page-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }
.labbtn { font-family: var(--f-sans); font-weight: 500; font-size: 28px; letter-spacing: normal; color: var(--md-on-surface); }
.post-btn { background: var(--md-primary); border: none; color: var(--md-on-primary); letter-spacing: normal; }
.post-btn:hover { background: var(--md-primary); }
.cat-tabs { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; }
.cat { padding: 8px 16px; cursor: pointer; font-size: 14px; letter-spacing: normal; color: var(--md-on-surface-variant); border-bottom: 1px solid transparent; transition: background 150ms, border-color 150ms, box-shadow 150ms;  min-height: 44px;  border-radius: 999px;  border: 1px solid var(--md-outline);  background: transparent; }
.cat:hover { color: var(--md-on-surface); }
.cat.on { border-bottom-color: var(--md-primary);  background: var(--md-primary-container); ;
  color: var(--md-on-primary-container);
  border-color: var(--md-primary-container);
}
.blog-list { margin-top: 12px; }
.blog-card { display: flex; gap: 16px; padding: 24px; background: var(--md-surface-container-lowest); border: 1px solid var(--md-outline-variant); border-radius: 24px; margin-bottom: 14px; box-shadow: var(--shadow-sm); cursor: pointer; transition: background 150ms, border-color 150ms, box-shadow 150ms; }
.blog-card:hover { box-shadow: var(--shadow-sm); border-color: var(--md-primary); }
.blog-card .cover { width: 120px; height: 90px; flex-shrink: 0; border-radius: 16px; overflow: hidden; }
.blog-card .cover img { width: 100%; height: 100%; object-fit: cover; }
.bc-body { flex: 1; min-width: 0; }
.bc-title { font-size: 20px; letter-spacing: normal; color: var(--md-on-surface); margin-bottom: 8px; }
.bc-meta { font-size: 13px; display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }
.bc-avatar { width: 20px; height: 20px; border-radius: 50%; object-fit: cover; }
.bc-content { font-size: 15px; color: var(--md-on-surface-variant); line-height: 1.7; }
.ell2 { display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
.empty-state { text-align: center; padding: 40px; }
.pagination-bar { display: flex; justify-content: center; margin-top: 20px; }

.blog-detail { max-height: 70vh; overflow-y: auto; padding-right: 8px; }
.blog-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; font-size: 13px; }
.blog-cover { margin-bottom: 16px; }
.blog-cover img { max-width: 100%; border-radius: 12px; }
.blog-content { white-space: pre-wrap; line-height: 2; color: var(--md-on-surface); }
.blog-poem { margin: 16px 0; padding: 12px 18px; border-left: 3px solid var(--md-primary); background: var(--md-surface-container-low); color: var(--md-on-surface); letter-spacing: normal; }
.blog-actions { margin: 18px 0; text-align: center; }
.cm-lab { font-size: 14px; letter-spacing: normal; color: var(--md-on-surface); margin: 18px 0 12px; border-top: 1px dashed var(--md-outline-variant); padding-top: 14px; }
.cm-item { display: flex; gap: 10px; padding: 12px 0; border-bottom: 1px dashed var(--md-outline-variant); }
.cm-avatar { width: 32px; height: 32px; border-radius: 50%; object-fit: cover; flex-shrink: 0; }
.cm-avatar.sm { width: 24px; height: 24px; }
.cm-body { flex: 1; min-width: 0; }
.cm-user { font-size: 13px; color: var(--md-on-surface); margin-bottom: 4px; display: flex; align-items: center; gap: 8px;  flex-wrap: wrap; }
.cm-time { font-size: 13px; }
.cm-text { font-size: 14px; color: var(--md-on-surface); line-height: 1.7; white-space: pre-wrap; }
.cm-child { display: flex; gap: 8px; margin-top: 10px; padding: 10px; background: var(--md-surface-container-low); border-radius: 12px; }
.cm-ops { display: flex; gap: 14px; margin-top: 6px; }
.cm-ops .op { font-size: 13px; color: var(--md-on-surface-variant); cursor: pointer; user-select: none; }
.cm-ops .op:hover { color: var(--md-primary); }
.hint { color: var(--md-on-surface-variant); font-size: 13px; text-align: center; padding: 12px; }
.cm-input { display: flex; flex-direction: column; gap: 8px; margin-top: 16px; }
.cm-input-row { display: flex; gap: 10px;  width: 100%; }
.replying { font-size: 13px; color: var(--md-primary); background: var(--md-error-container); padding: 4px 10px; border-radius: 12px; align-self: flex-start; }
.replying .cancel { margin-left: 8px; cursor: pointer; color: var(--md-on-surface-variant); }
.replying .cancel:hover { color: var(--md-primary); }
:deep(.el-dialog) { border-radius: 12px; }
:deep(.el-dialog__title) { font-family: var(--f-sans); letter-spacing: normal; font-size: 20px; }

:deep(.el-button) { min-height: 44px; border-radius: 999px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-input__wrapper) { min-height: 48px; border-radius: 12px; }
:deep(.el-textarea__inner) { border-radius: 12px; font-size: 15px; }
:deep(.el-tabs__item) { min-height: 48px; font-family: var(--f-sans); letter-spacing: normal; }
:deep(.el-dialog) { max-width: calc(100vw - 32px); border-radius: 28px; }
.form-error { font-size: 14px; line-height: 1.5; color: var(--md-error); background: var(--md-error-container); border-radius: 12px; padding: 12px 16px; }

@media (max-width: 600px) { .page-head { gap: 12px; flex-wrap: wrap; } .blog-card { padding: 16px; gap: 12px; } .blog-card .cover { width: 80px; height: 80px; } .cm-input-row { flex-wrap: wrap; } .cm-input-row .el-input { flex-basis: 100%; } }
.cm-ops button.op { min-height: 44px; border: 0; border-radius: 999px; background: transparent; padding: 8px 12px; font-family: var(--f-sans); color: var(--md-primary); } .replying .cancel { min-width: 44px; min-height: 44px; border: none; background: transparent; color: inherit; border-radius: 999px; }
</style>
