import request from '@/utils/request'
import type { WriterVo, Poem, PageResult } from './types'

export const getWriterCount = () => request.get<number, number>('/user/writer/GetWriterCount')
export const getAllWriterNames = () => request.get<string[], string[]>('/user/writer/GetAllWriterNames')
export const getAllDynasties = () => request.get<string[], string[]>('/user/writer/GetAllDynasties')
export const getImageAndSimpleIntro = (name: string) =>
  request.get<WriterVo, WriterVo>('/user/writer/imageAndSimpleIntro', { params: { name } })
export const getDetailIntro = (name: string) =>
  request.get<string, string>('/user/writer/detailIntro', { params: { name } })
export const getWritersByDynastyFull = (dynasty: string) =>
  request.get<WriterVo[], WriterVo[]>('/user/writer/GetWritersByDynastyFull', { params: { dynasty } })
export const getWritersByDynasty = (dynasty: string) =>
  request.get<string[], string[]>('/user/writer/GetWritersByDynasty', { params: { dynasty } })
export const getPoemsByWriter = (writer: string) =>
  request.get<Poem[], Poem[]>('/user/writer/GetPoemsByWriter', { params: { writer } })
export const getRandomWriters = () => request.get<WriterVo[], WriterVo[]>('/user/writer/GetRandomWriters')
export const getWriterAndPoemsById = (id: number) =>
  request.get<any, any>('/user/writer/GetWriterAndPoemsById', { params: { id } })
export const getFamousLinesByWriterId = (id: number) =>
  request.get<Poem, Poem>('/user/writer/GetFamousLinesByWriterId', { params: { id } })
export const getWritersByPage = (pageNum = 1, pageSize = 15) =>
  request.get<PageResult<WriterVo>, PageResult<WriterVo>>('/user/writer/GetWritersByPage', { params: { pageNum, pageSize } })