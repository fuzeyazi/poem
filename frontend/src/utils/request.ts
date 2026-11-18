import axios, { type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/store/user'
import router from '@/router'

// 后端统一返回：{ code, msg, data }，code=1 成功，0 失败
export interface Result<T = any> {
  code: number
  msg?: string
  data?: T
}

const service = axios.create({
  baseURL: '/',
  timeout: 15000,
})

// 请求拦截：自动塞 token 头
service.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const userStore = useUserStore()
    if (userStore.token) {
      config.headers['token'] = userStore.token
    }
    return config
  },
  (error) => Promise.reject(error),
)

// 响应拦截：按 code 字段分流
service.interceptors.response.use(
  (response: AxiosResponse<Result>) => {
    const res = response.data
    // 非统一结构（如验证码图片、流）直接放行
    if (res === null || res === undefined || typeof res.code === 'undefined') {
      return response.data
    }
    if (res.code === 1) {
      return res.data as any
    }
    // code=0 业务失败
    ElMessage.error(res.msg || '请求失败')
    return Promise.reject(new Error(res.msg || '请求失败'))
  },
  (error) => {
    const status = error.response?.status
    if (status === 401) {
      ElMessage.error('登录已过期，请重新登录')
      const userStore = useUserStore()
      userStore.clearToken()
      router.push('/login')
      return Promise.reject(error)
    }
    // 透传 HTTP 错误给组件处理，标记 msg 供取用
    const data = error.response?.data
    error._httpMsg = data?.message || data?.msg || data?.error || error.message
    ElMessage.error(String(error._httpMsg || '网络异常，请稍后重试'))
    return Promise.reject(error)
  },
)

export default service



