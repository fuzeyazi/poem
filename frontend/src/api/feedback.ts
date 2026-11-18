import request from '@/utils/request'
import type { FeedBack } from './types'

export const addFeedback = (data: { userid?: number; message: string }) =>
  request.post<string, string>('/user/FeedBack/addfeedback', data)

export const getReply = (id: number) => request.get<string, string>(`/user/FeedBack/getReply/${id}`)

// 获取当前登录用户自己的反馈历史
export const getAllFeedBack = () => request.get<FeedBack[], FeedBack[]>('/user/FeedBack/getAllFeedBack')
