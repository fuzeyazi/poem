import request from '@/utils/request'
import type { PageResult, Poem } from './types'

/* 诗词 */
export const getPoetryCount = () => request.get<number, number>('/user/poetry/GetCount')
export const getAllPoemName = () => request.get<string[], string[]>('/user/poetry/GetAllPoemName')
export const getAllDynasty = () => request.get<string[], string[]>('/user/poetry/GetAllDynasty')
export const getVeryGoodPoem = () => request.get<Poem, Poem>('/user/poetry/GetVeryGoodPoem')
export const getRandomPoem = () => request.get<Poem[], Poem[]>('/user/poetry/GetPoemDateRondom')
export const getContentById = (id: number) => request.get<Poem, Poem>(`/user/poetry/GetContentById/${id}`)
export const getPoemByDynasty = (dynasty: string) =>
  request.get<Poem[], Poem[]>(`/user/poetry/GetPoemByDynasty/${dynasty}`)
// 分页按标题
export const getPoemByTitle = (title: string, pageNum = 1, pageSize = 20) =>
  request.get<PageResult<Poem>, PageResult<Poem>>('/user/poetry/GetPoembyTitle', { params: { title, pageNum, pageSize } })
// 分页按朝代
export const getPoemsByDynasty = (dynasty: string, pageNum = 1, pageSize = 20) =>
  request.get<PageResult<Poem>, PageResult<Poem>>('/user/poetry/GetPoemsByDynasty', { params: { dynasty, pageNum, pageSize } })
// 分页全量
export const getPoemPage = (pageNum = 1, pageSize = 20) =>
  request.get<PageResult<Poem>, PageResult<Poem>>('/user/poetry/GetPoemPage', { params: { pageNum, pageSize } })
// 朝代与诗 grouped
export const getDynastyAndPoem = () => request.get<any[], any[]>('/user/poetry/GetDynastyandpoem')
// 搜索自动补全（标题+诗人名，≤8 条；后端 ZSet 前缀查询，Redis 故障降级 idx_title）
export const getSearchSuggest = (kw: string) =>
  request.get<string[], string[]>('/user/poetry/suggest', { params: { kw } })
// 24h 滚动热搜 Top10（后端已防刷：同用户同词 60s 去重）
export const getHotSearch = () =>
  request.get<{ kw: string; score: number }[], { kw: string; score: number }[]>('/user/poetry/hotsearch')
// 复习完成：答对触发，reviewCount+1 且 next_review_date 按 1/3/7/14/30 天推进（§3.1）
export const poemReviewEnd = (poemid: number) =>
  request.get<any, any>('/user/poetry/query/end', { params: { kk: 1, poemid } })
