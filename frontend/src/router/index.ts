import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/store/user'

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    // PoetryList restores its cached document position for an explicit reader return.
    if (to.name === 'poetry' && from.name === 'poem-detail') return false
    if (to.path === from.path) return false
    return { top: 0 }
  },
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/Login.vue'), meta: { public: true } },
    { path: '/', redirect: '/poetry' },
    { path: '/poetry', name: 'poetry', component: () => import('@/views/PoetryList.vue') },
    { path: '/poem/:title', name: 'poem-detail', component: () => import('@/views/PoemDetail.vue') },
    { path: '/writers', name: 'writers', component: () => import('@/views/Writers.vue') },
    { path: '/rhesis', name: 'rhesis', component: () => import('@/views/Rhesis.vue') },
    { path: '/forum', name: 'forum', component: () => import('@/views/Forum.vue') },
    { path: '/review', name: 'review', component: () => import('@/views/ReviewToday.vue') },
    { path: '/feedback', name: 'feedback', component: () => import('@/views/Feedback.vue') },
    { path: '/notice', name: 'notice', component: () => import('@/views/Notice.vue') },
    { path: '/center', name: 'center', component: () => import('@/views/UserCenter.vue') },
    { path: '/ai', name: 'ai', component: () => import('@/views/AiChat.vue') },
    { path: '/console', name: 'console', component: () => import('@/views/Console.vue'), meta: { public: true } },
    { path: '/console/content', name: 'console-content', component: () => import('@/views/ContentAdmin.vue'), meta: { public: true } },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/views/NotFound.vue'), meta: { public: true } },
  ],
})

router.beforeEach((to) => {
  const userStore = useUserStore()
  if (to.meta.public) return true
  if (!userStore.token) return { name: 'login', query: { redirect: to.fullPath } }
  return true
})

export default router
