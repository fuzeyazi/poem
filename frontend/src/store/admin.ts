import { defineStore } from 'pinia'
import { ref } from 'vue'

// 管理端凭证（与用户端 token 隔离：admin 密钥签发，用于 /admin/** 与 agent /api/admin/**）
export const useAdminStore = defineStore(
  'admin',
  () => {
    const token = ref('')
    const userName = ref('')
    const setAdmin = (t: string, n: string) => { token.value = t; userName.value = n }
    const clearAdmin = () => { token.value = ''; userName.value = '' }
    return { token, userName, setAdmin, clearAdmin }
  },
  { persist: true },
)
