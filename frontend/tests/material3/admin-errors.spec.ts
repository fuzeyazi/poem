import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import axios, { AxiosError, type AxiosAdapter } from 'axios'
import { createPinia, setActivePinia } from 'pinia'
import { ElMessage } from 'element-plus'
import { useAdminStore } from '@/store/admin'

let api: typeof import('@/api/adminApi')
let adapter: AxiosAdapter
beforeAll(async () => {
  const create = axios.create.bind(axios)
  vi.spyOn(axios, 'create').mockImplementation(config => {
    const instance = create(config)
    instance.defaults.adapter = config => adapter(config)
    return instance
  })
  api = await import('@/api/adminApi')
})
beforeEach(() => {
  setActivePinia(createPinia())
  useAdminStore().setAdmin('test-admin-token', '测试管理员')
})
afterEach(() => { ElMessage.closeAll(); document.body.innerHTML = '' })
afterAll(() => vi.restoreAllMocks())

describe('Admin request failure feedback', () => {
  it.each([
    { name: 'HTTP 500', status: 500, code: AxiosError.ERR_BAD_RESPONSE },
    { name: 'timeout', status: undefined, code: AxiosError.ECONNABORTED },
    { name: 'offline', status: undefined, code: AxiosError.ERR_NETWORK },
  ])('shows exactly one visible error for $name and retains the admin session', async ({ status, code }) => {
    adapter = async config => {
      const response = status ? { data: {}, status, statusText: 'Failure', headers: {}, config } : undefined
      throw new AxiosError('simulated request failure', code, config, undefined, response)
    }
    await expect(api.cacheStats()).rejects.toBeInstanceOf(AxiosError)
    await vi.waitFor(() => expect(document.querySelectorAll('.el-message--error')).toHaveLength(1))
    expect(document.querySelector('.el-message--error')?.textContent?.trim()).toBeTruthy()
    expect(useAdminStore().token).toBe('test-admin-token')
  })

  it('keeps the existing 401 feedback and clears credentials without a second notification', async () => {
    adapter = async config => { throw new AxiosError('unauthorized', AxiosError.ERR_BAD_REQUEST, config, undefined, { data: {}, status: 401, statusText: 'Unauthorized', headers: {}, config }) }
    await expect(api.cacheStats()).rejects.toBeInstanceOf(AxiosError)
    await vi.waitFor(() => expect(document.querySelectorAll('.el-message--error')).toHaveLength(1))
    expect(document.body.textContent).toContain('管理端凭证无效')
    expect(useAdminStore().token).toBe('')
  })

  it('reports a rejected business response once through the same request owner', async () => {
    adapter = async config => ({ data: { code: 0, msg: '操作未完成' }, status: 200, statusText: 'OK', headers: {}, config })
    await expect(api.cacheStats()).rejects.toThrow('操作未完成')
    await vi.waitFor(() => expect(document.querySelectorAll('.el-message--error')).toHaveLength(1))
    expect(document.body.textContent).toContain('操作未完成')
  })
})
