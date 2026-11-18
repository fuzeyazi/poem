/* ===== 通用类型 ===== */
export interface Result<T = any> { code: number; msg?: string; data?: T }
export interface PageResult<T = any> { total: number; records: T[] }

export interface Poem {
  id?: number
  title: string
  dynasty?: string
  writer?: string
  type?: string
  content?: string
  remarks?: string | null
  translation?: string
  shangxi?: string
  audiourl?: string
  islike?: number | null
}
export interface Rhesis { id?: number; name?: string; fromm?: string }
export interface WriterVo {
  id?: number; name?: string; headImageUrl?: string
  simpleIntro?: string; detailIntro?: string
}
export interface CommentVo { id?: number; content?: string; parentId?: number; username?: string; createtime?: string }
export interface FeedBack { id?: number; message?: string; reply?: string; createtime?: string }
export interface NoticeDto { id?: number; name?: string; contents?: string }
export interface UserVo {
  id?: number; username?: string; name?: string; openid?: string
  touxiang?: string; token?: string; degree?: string
}
export interface UserBook { bookid?: number; userid?: number; bookname?: string; description?: string; sum?: number; end?: number }
export interface PoemBlogVo {
  id?: number; title?: string; images?: string; content?: string
  type?: string; dianzans?: number; username?: string; userid?: number
}
/* 论坛评论（后端 FabaCommnetVo，两级模型：主评论 + children；parentId 已由后端归一到根评论） */
export interface ForumCommentVo {
  id?: number
  blogid?: number
  userId?: number
  name?: string
  touxiang?: string
  context?: string
  createTiem?: string
  liked?: number
  conment?: number
  parentId?: number | null
  replyToUserId?: number | null
  replyToUserName?: string | null
  tagerrName?: string
  children?: ForumCommentVo[]
}
/* 今日应复习（后端 TodayReviewVo，§3.1；dueStage=轮次文案如"第3轮·7天"） */
export interface TodayReviewVo {
  poemid: number
  title: string
  writer?: string
  content?: string
  dynasty?: string
  reviewCount?: number
  nextReviewDate?: string | null
  dueStage?: string
}
