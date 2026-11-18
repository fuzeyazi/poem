import request from '@/utils/request'
import type { PageResult, NoticeDto } from './types'

export const addNotice = (data: NoticeDto) => request.post<any, any>('/notice/add', data)
export const deleteNotice = (ids: number[]) => request.post<any, any>('/notice/delete', ids)
export const getNoticeList = (pageNum = 1, pageSize = 10) =>
  request.get<PageResult, PageResult>('/notice/getList', { params: { pageNum, pageSize } })
export const updateNotice = (data: NoticeDto) => request.post<any, any>('/notice/update', data)
export const getNotice = () => request.get<NoticeDto[], NoticeDto[]>('/notice/get')