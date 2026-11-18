import { watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Client, type IMessage } from '@stomp/stompjs'
import { useUserStore } from '@/store/user'

/* 复习提醒：全局 STOMP 连接，订阅 /topic/review.{userId}（§3.1）。
   登录后连接并订阅，登出断开；消息 {type:"review_remind",count,date} → toast。
   连续失败时重连间隔指数退避（封顶 120s），后端网关 WS 不可用时不刷屏。 */
let client: Client | null = null
let failCount = 0

export function setupReviewRemind() {
  const userStore = useUserStore()
  const connect = () => {
    if (client) { client.deactivate(); client = null }
    const uid = userStore.userId
    if (!userStore.token || !uid) return
    try {
      client = new Client({
        brokerURL: `ws://${location.host}/ws/websocket`,
        reconnectDelay: 6000,
        onConnect: () => {
          failCount = 0
          if (client) client.reconnectDelay = 6000
          client?.subscribe(`/topic/review.${uid}`, (msg: IMessage) => {
            try {
              const d = JSON.parse(msg.body)
              if (d.type === 'review_remind' && d.count) {
                ElMessage.info(`今天有 ${d.count} 首诗待复习`)
              }
            } catch { /* 忽略坏帧 */ }
          })
        },
        onWebSocketClose: () => {
          failCount++
          if (client) client.reconnectDelay = Math.min(6000 * failCount, 120000)
        },
      })
      client.activate()
    } catch { /* 推送不可用不影响主流程 */ }
  }
  watch(() => userStore.token, connect, { immediate: true })
}
