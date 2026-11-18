import axios, { type AxiosInstance } from 'axios'
import { ElMessage } from 'element-plus'
import { useAdminStore } from '@/store/admin'

// 管理面专用实例：header 注入管理端 token（区别于用户端 request.ts）
// Java /admin/**（登录鉴权）与 agent /api/admin/**（审核/成本/审计，vite 代理直达 8000）
const http: AxiosInstance = axios.create({ baseURL: '/', timeout: 15000 })

http.interceptors.request.use((config) => {
  const admin = useAdminStore()
  if (admin.token) config.headers['token'] = admin.token
  return config
})

http.interceptors.response.use(
  (response) => {
    const res = response.data
    if (res === null || res === undefined || typeof res.code === 'undefined') return res
    if (res.code === 1) return res.data
    ElMessage.error(res.msg || '请求失败')
    return Promise.reject(new Error(res.msg || '请求失败'))
  },
  (error) => {
    if (error.response?.status === 401) {
      ElMessage.error('管理端凭证无效，请重新登录')
      useAdminStore().clearAdmin()
    } else {
      const fallback = error.code === 'ECONNABORTED' ? '请求超时，请重试'
        : error.response ? '请求失败，请稍后重试' : '网络连接失败，请检查网络后重试'
      ElMessage.error(error.response?.data?.msg || fallback)
    }
    return Promise.reject(error)
  },
)

/* ---- Java 管理端鉴权（验证码 → 登录换 token） ---- */
export const adminGetCode = () => http.get<any, any>('/admin/getCode')
export const adminLogin = (data: { username: string; password: string; code: string; codeKey: string }) =>
  http.post<any, any>('/admin/login', data)

/* ---- Agent 管理面：飞轮审核 ---- */
export const reviewList = (status = 'pending', limit = 50, offset = 0) =>
  http.get<any, any>('/api/admin/review', { params: { status, limit, offset } })
export const reviewDetail = (id: number) => http.get<any, any>(`/api/admin/review/${id}`)
export const reviewApprove = (id: number, body: { standard_question?: string; approved_answer: string }) =>
  http.post<any, any>(`/api/admin/review/${id}/approve`, body)
export const reviewReject = (id: number) => http.post<any, any>(`/api/admin/review/${id}/reject`)

/* ---- Agent 管理面：成本报表 / 工具审计 ---- */
export const costReport = (days = 14) => http.get<any, any>('/api/admin/cost', { params: { days } })
export const auditList = (params: { limit?: number; offset?: number; tool_name?: string; status?: string }) =>
  http.get<any, any>('/api/admin/audit', { params })

/* ---- 内容管理：诗词 ---- */
export const poemPage = (pageNum = 1, pageSize = 10) =>
  http.get<any, any>('/admin/potry/GetPoemPage', { params: { pageNum, pageSize } })
export const poemAdd = (data: any) => http.post<any, any>('/admin/potry/add', data)
export const poemUpdate = (data: any) => http.post<any, any>('/admin/potry/update', data)
export const poemDelete = (ids: number[]) => http.post<any, any>('/admin/potry/delete', null, { params: { ids } , paramsSerializer: { indexes: null } as any })

/* ---- 内容管理：诗人 ---- */
export const writerPage = (pageNum = 1, pageSize = 15) =>
  http.get<any, any>('/admin/writer/GetWritersByPage', { params: { pageNum, pageSize } })
export const writerAdd = (data: any) => http.post<any, any>('/admin/writer/add', data)
export const writerUpdate = (data: any) => http.post<any, any>('/admin/writer/update', data)
export const writerDelete = (ids: number[]) => http.post<any, any>('/admin/writer/delete', null, { params: { ids } })

/* ---- 内容管理：名句 ---- */
export const rhesisPage = (pageNum = 1, pageSize = 10) =>
  http.get<any, any>('/admin/rhesis/GetAll', { params: { pageNum, pageSize } })
export const rhesisAdd = (data: any) => http.post<any, any>('/admin/rhesis/add', data)
export const rhesisUpdate = (data: any) => http.post<any, any>('/admin/rhesis/update', data)
export const rhesisDelete = (ids: number[]) => http.post<any, any>('/admin/rhesis/delete', null, { params: { ids } })

/* ---- 内容管理：帖子与评论 ---- */
export const blogPage = (pageNum = 1, pageSize = 10) =>
  http.get<any, any>('/admin/blog/getAllBlog', { params: { pageNum, pageSize } })
export const blogDelete = (ids: number[]) => http.post<any, any>('/admin/blog/deleteBlog', null, { params: { ids } })
export const blogComments = (blogid: number, pageNum = 1, pageSize = 20) =>
  http.get<any, any>('/admin/blog/comments', { params: { blogid, pageNum, pageSize } })
export const commentDelete = (ids: number[]) =>
  http.post<any, any>('/admin/blog/deleteComment', null, { params: { ids } })

/* ---- 内容管理：用户 ---- */
export const userPage = (pageNum = 1, pageSize = 10) =>
  http.get<any, any>('/admin/getAll', { params: { pageNum, pageSize } })
export const userDisable = (status: number, id: number) =>
  http.post<any, any>(`/admin/disable/${status}`, null, { params: { id } })

/* ---- 内容管理：公告 ---- */
export const noticePage = (pageNum = 1, pageSize = 10) =>
  http.get<any, any>('/notice/getList', { params: { pageNum, pageSize } })
export const noticeAdd = (data: any) => http.post<any, any>('/notice/add', data)
export const noticeUpdate = (data: any) => http.post<any, any>('/notice/update', data)
export const noticeDelete = (ids: number[]) => http.post<any, any>('/notice/delete', null, { params: { ids } })

/* ---- Agent 管理面：知识库同步（MySQL↔Milvus 一致性） ---- */
export const kbSyncStats = () => http.get<any, any>('/api/admin/kb/syncstats')
export const kbSyncTrigger = (title?: string) =>
  http.post<any, any>('/api/admin/kb/sync', null, title ? { params: { title } } : undefined)
/* ---- 内容管理：用户反馈 ---- */
export const adminFeedbackPage = (pageNum = 1, pageSize = 15) =>
  http.get<any, any>('/admin/feedback/page', { params: { pageNum, pageSize } })
export const adminFeedbackAll = () =>
  http.get<any, any>('/admin/feedback/getAllFeedBack')
export const adminFeedbackDelete = (id: number) =>
  http.delete<any, any>(`/admin/feedback/${id}`)
export const adminFeedbackReply = (data: { feedbackid: number; message: string; userid?: number }) =>
  http.put<any, any>('/admin/feedback/reply', data)

/* ---- 运维观测：多级缓存管控 ---- */
export const cacheStats = () => http.get<any, any>('/admin/cache/stats')
export const cacheWarmup = () => http.post<any, any>('/admin/cache/warmup')
export const cacheClear = () => http.post<any, any>('/admin/cache/clear')
