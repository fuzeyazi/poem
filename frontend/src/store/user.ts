import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore(
  'user',
  () => {
    const token = ref<string>('')
    const userId = ref<number | null>(null)
    const userName = ref<string>('')

    const setLogin = (t: string, id: number, name: string) => {
      token.value = t
      userId.value = id
      userName.value = name
    }
    const clearToken = () => {
      token.value = ''
      userId.value = null
      userName.value = ''
    }
    return { token, userId, userName, setLogin, clearToken }
  },
  { persist: true },
)