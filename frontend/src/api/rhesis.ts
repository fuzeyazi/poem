import request from '@/utils/request'
import type { Rhesis } from './types'

export const getRhesisCount = () => request.get<number, number>('/user/rhesis/GetCount')
export const getRhesisByKey = (keyword: string) =>
  request.get<Rhesis[], Rhesis[]>(`/user/rhesis/GetRhesisByKey/${keyword}`)
export const getRandomRhesis = () => request.get<Rhesis[], Rhesis[]>('/user/rhesis/GetRhesisDateRondom')
export const getVeryGoodRhesis = () => request.get<Rhesis, Rhesis>('/user/rhesis/GetVeryGoodRhesis')
export const getRhesisContentById = (id: number) =>
  request.get<Rhesis, Rhesis>(`/user/rhesis/GetRhesisContentById/${id}`)