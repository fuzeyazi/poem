import request from '@/utils/request'
import type { UserVo, UserBook, Poem, Rhesis, PageResult, TodayReviewVo } from './types'

/* 鉴权 */
export const login = (data: { username: string; password: string }) =>
  request.post<UserVo, UserVo>('/user/login', data)
export const register = (data: {
  username: string; password: string; email?: string; name?: string
  phone?: string; sex?: string; degree?: string
}) => request.post<string, string>('/user/register', data)
export const loginByEmail = (data: { email: string; code: string }) =>
  request.post<UserVo, UserVo>('/user/login/email', data)
export const sendCode = (phone: string) =>
  request.post<string, string>('/user/login/code', null, { params: { phone } })
export const forget = (data: { email: string; code: string; password: string }) =>
  request.get<string, string>('/user/forget', { params: data })

/* 个人信息 */
export const getMessageById = () => request.get<any, any>('/user/getmassagebyid')
export const updateMessageById = (data: any) => request.put<string, string>('/user/updatemessagebyid', data)

/* 收藏诗词 */
export const collectPoem = (data: { userid?: number; poemid: number }) =>
  request.post<string, string>('/user/collect/addpem', data)
export const uncollectPoem = (data: { userid?: number; poemid: number }) =>
  request.delete<string, string>('/user/collect/deletepem', { data })
export const getCollectIds = () => request.get<number[], number[]>('/user/collect/ids')
export const getCollectPoems = () => request.get<Poem[], Poem[]>('/user/collect')

/* 收藏名句 */
export const collectRhesis = (data: { userid?: number; rhesisid: number }) =>
  request.post<string, string>('/user/collect/addrhesis', data)
export const uncollectRhesis = (data: { userid?: number; rhesisid: number }) =>
  request.delete<string, string>('/user/collect/deleterhesis', { data })
export const getCollectRhesisIds = (id: number) =>
  request.get<number[], number[]>(`/user/collect/rhesisids/${id}`)
export const getCollectRhesis = (id: number) =>
  request.get<Rhesis[], Rhesis[]>(`/user/collectRhesis/${id}`)

/* 学习计划（诗集本） */
export const bookStart = (data: UserBook) => request.post<string, string>('/user/book/statr', data)
export const bookAdd = (data: { bookname: string; description: string }) =>
  request.post<string, string>('/user/book/add', data)
export const bookAddPoem = (data: { bookid: number; poemid: number }) =>
  request.post<string, string>('/user/book/addpoem', data)
export const bookShow = () => request.get<UserBook[], UserBook[]>('/user/book/show')
export const bookShowPoem = (bookid: number) =>
  request.get<Poem[], Poem[]>(`/user/book/showpoem/${bookid}`)
export const bookStartReview = (bookId: number, much = 1) =>
  request.post<string, string>('/user/book/start', null, { params: { bookId, much } })
export const bookShowPlan = (bookid: number) =>
  request.get<any[], any[]>(`/user/book/showplan/${bookid}`)

/* 我的评论 */
export const myComments = () => request.get<any[], any[]>('/user/user/comment')
export const deleteMyComment = (commentid: number) =>
  request.delete<string, string>(`/user/user/comment/delete/${commentid}`)
/* 艾宾浩斯复习（§3.1：今日应复习/红点计数/提醒日志） */
/** 背诵完成(kk=1): SRS轮次推进(答对接口复用) */
export const reciteDone = (poemid: number) =>
  request.get<string, string>('/user/poetry/query/end', { params: { kk: 1, poemid } })
export const bookToday = (bookid: number) =>
  request.get<TodayReviewVo[], TodayReviewVo[]>('/user/book/today', { params: { bookid } })
export const getRemindCount = () =>
  request.get<{ count: number }, { count: number }>('/user/book/remindcount')
export const getRemindLog = () =>
  request.get<{ date: string; count: number }[], { date: string; count: number }[]>('/user/book/remindlog')
