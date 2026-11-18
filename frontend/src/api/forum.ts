import request from '@/utils/request'
import type { PageResult, Poem, ForumCommentVo } from './types'

export const postBlog = (data: {
  title?: string; images?: string; content?: string; type?: string; poemId?: number; poemWord?: string
}) => request.post<any, any>('/user/luntan/fabutiezi', data)
export const updateImage = (file: File) => {
  const fd = new FormData(); fd.append('file', file)
  return request.post<any, any>('/user/luntan/updateImage', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
}
export const selectTiez = (type1: number, pageNum = 1, pageSize = 4) =>
  request.get<PageResult, PageResult>('/user/luntan/selecttiez', { params: { type1, pageNum, pageSize } })
export const selectXiangxi = (blogid: number) =>
  request.get<any, any>('/user/luntan/selectxiangxi', { params: { blogid } })
export const dianzan = (blogid: number) =>
  request.get<string, string>('/user/luntan/dianzan', { params: { blogid } })
export const dianzanRank = (blogid: number) =>
  request.get<any[], any[]>('/user/luntan/dianzanrank', { params: { blogid } })
export const isFollow = (followUserid: number) =>
  request.get<string, string>('/user/luntan/isguanzhu', { params: { followUserid } })
export const follow = (followUserid: number, isFollow: boolean) =>
  request.get<any, any>('/user/luntan/guanzhu', { params: { followUserid, isFollow } })
export const selectUser = (followid: number) =>
  request.get<any, any>(`/user/luntan/select/user/${followid}`)
export const selectUserBlog = (followid: number, pageNum = 1, pageSize = 4) =>
  request.get<PageResult, PageResult>(`/user/luntan/select/blog/${followid}`, { params: { pageNum, pageSize } })
export const selectFollowed = (lasttimemax: number, offset = 0) =>
  request.get<any[], any[]>('/user/luntan/select/guanzhu', { params: { lasttimemax, offset } })
export const postForumComment = (data: { blogId?: number; context?: string; parentId?: number; tagerrName?: string }) =>
  request.post<any, any>('/user/luntan/fabacomment', data)
export const selectComments = (blogid: number) =>
  request.get<ForumCommentVo[], ForumCommentVo[]>('/user/luntan/selectConmmets', { params: { blogid } })
export const selectCommentsPage = (blogid: number, pageNum = 1, pageSize = 10) =>
  request.get<PageResult, PageResult>('/user/luntan/selectConmmets11', { params: { blogid, pageNum, pageSize } })
export const commentDianzan = (commentid: number) =>
  request.get<string, string>('/user/luntan/commentdianzan', { params: { commentid } })
export const selectForum = () => request.get<any[], any[]>('/user/luntan/select/forum')
export const searchForum = (content: string) =>
  request.get<any[], any[]>('/user/luntan/search', { params: { content } })