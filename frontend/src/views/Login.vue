<template>
  <div class="login-bg">
    <div class="seal-corner">诗</div>
    <el-card class="login-card" :body-style="{ padding: '0' }" shadow="never">
      <div class="login-head">
        <div class="lh-title">古诗文</div>
        <div class="lh-sub">POETRY · 经典诵读</div>
      </div>
      <div class="login-body">
        <el-tabs v-model="active" stretch>
          <el-tab-pane label="登录" name="login">
            <el-form :model="form" label-position="top" @submit.prevent="onLogin" :aria-busy="loading">
              <el-form-item label="用户名" :error="loginErrors.username">
                <el-input v-model="form.username" autocomplete="username" @input="loginErrors.username = ''" placeholder="请输入用户名" size="large" />
              </el-form-item>
              <el-form-item label="密码" :error="loginErrors.password">
                <el-input v-model="form.password" autocomplete="current-password" @input="loginErrors.password = ''" type="password" show-password placeholder="请输入密码" size="large" />
              </el-form-item>
              <p v-if="loginError" class="form-error" role="alert">{{ loginError }}</p>
              <el-button class="submit-btn" type="primary" native-type="submit" :loading="loading" :disabled="loading">{{ loading ? '登录中…' : '登录' }}</el-button>
            </el-form>
          </el-tab-pane>
          <el-tab-pane label="注册" name="register">
            <el-form :model="reg" label-position="top" @submit.prevent="onRegister" :aria-busy="regLoading">
              <el-form-item label="用户名" :error="registerErrors.username"><el-input v-model="reg.username" autocomplete="username" @input="registerErrors.username = ''" size="large" /></el-form-item>
              <el-form-item label="密码" :error="registerErrors.password"><el-input v-model="reg.password" autocomplete="new-password" @input="registerErrors.password = ''" type="password" show-password size="large" /></el-form-item>
              <el-form-item label="昵称"><el-input v-model="reg.name" autocomplete="nickname" size="large" /></el-form-item>
              <el-form-item label="邮箱（选填）" :error="registerErrors.email"><el-input v-model="reg.email" autocomplete="email" inputmode="email" @input="registerErrors.email = ''" size="large" /></el-form-item>
              <el-form-item label="手机"><el-input v-model="reg.phone" autocomplete="tel" inputmode="tel" size="large" /></el-form-item>
              <el-form-item label="性别">
                <el-radio-group v-model="reg.sex">
                  <el-radio value="男">男</el-radio>
                  <el-radio value="女">女</el-radio>
                </el-radio-group>
              </el-form-item>
              <p v-if="registerError" class="form-error" role="alert">{{ registerError }}</p>
              <el-button class="submit-btn" type="primary" native-type="submit" :loading="regLoading" :disabled="regLoading">{{ regLoading ? '注册中…' : '注册' }}</el-button>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-card>
    <p class="login-foot">© 诗词库 · 经典流传</p>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, shallowRef } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login, register } from '@/api/user'
import { useUserStore } from '@/store/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const active = ref('login')
const loading = ref(false)
const regLoading = ref(false)
const form = reactive({ username: '', password: '' })
const reg = reactive({ username: '', password: '', name: '', email: '', phone: '', sex: '男' })

const loginErrors = reactive({ username: '', password: '' })
const registerErrors = reactive({ username: '', password: '', email: '' })
const loginError = shallowRef('')
const registerError = shallowRef('')
const onLogin = async () => {
  if (loading.value) return
  loginError.value = ''
  loginErrors.username = form.username.trim() ? '' : '请输入用户名'
  loginErrors.password = form.password ? '' : '请输入密码'
  if (loginErrors.username || loginErrors.password) return
  loading.value = true
  try {
    const data = await login({ username: form.username.trim(), password: form.password })
    userStore.setLogin(data.token || '', data.id ?? 0, data.username || '')
    ElMessage.success('登录成功')
    router.push((route.query.redirect as string) || '/poetry')
  } catch { loginError.value = '登录失败，请检查用户名和密码后重试' } finally { loading.value = false }
}
const onRegister = async () => {
  if (regLoading.value) return
  registerError.value = ''
  registerErrors.username = reg.username.trim() ? '' : '请输入用户名'
  registerErrors.password = reg.password ? '' : '请输入密码'
  registerErrors.email = !reg.email.trim() || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(reg.email.trim()) ? '' : '请输入有效邮箱'
  if (Object.values(registerErrors).some(Boolean)) return
  regLoading.value = true
  try {
    await register({ ...reg, username: reg.username.trim(), email: reg.email.trim() })
    ElMessage.success('注册成功，请登录')
    form.username = reg.username; form.password = reg.password
    active.value = 'login'
  } catch { registerError.value = '注册失败，请检查信息后重试' } finally { regLoading.value = false }
}
</script>

<style scoped>
.login-bg { min-height: 100dvh; padding: 32px 16px; display: flex; flex-direction: column; align-items: center; justify-content: center; background: var(--md-surface); color: var(--md-on-surface); font-family: var(--f-sans); }
.seal-corner { display: grid; place-items: center; width: 56px; height: 56px; border-radius: 20px; background: var(--md-primary-container); color: var(--md-on-primary-container); font-size: 28px; margin-bottom: 24px; }
.login-card { width: min(100%, 440px); border: 1px solid var(--md-outline-variant); border-radius: 28px; background: var(--md-surface-container-lowest); box-shadow: var(--shadow-sm); overflow: hidden; }
.login-head { text-align: center; padding: 32px 24px 16px; }
.lh-title { font-size: 32px; line-height: 1.3; color: var(--md-on-surface); font-weight: 500; }
.lh-sub { font-size: 14px; color: var(--md-on-surface-variant); margin-top: 8px; }
.login-body { padding: 8px 32px 32px; }
.submit-btn { width: 100%; margin-top: 8px; min-height: 48px; background: var(--md-primary); border-color: var(--md-primary); color: var(--md-on-primary); font-size: 16px; border-radius: 999px; }
.submit-btn:hover { background: color-mix(in srgb, var(--md-primary) 90%, var(--md-on-primary)); }
.login-foot { margin: 24px 0 0; font-size: 13px; color: var(--md-on-surface-variant); }
.form-error { color: var(--md-error); background: var(--md-error-container); padding: 12px 16px; border-radius: 12px; font-size: 14px; line-height: 1.5; }
:deep(.el-tabs__item) { font-size: 16px; font-family: var(--f-sans); height: 48px; }
:deep(.el-input__wrapper) { min-height: 48px; border-radius: 12px; background: var(--md-surface-container-lowest); box-shadow: 0 0 0 1px var(--md-outline) inset; }
:deep(.el-input__wrapper.is-focus) { box-shadow: 0 0 0 2px var(--md-primary) inset; }
:deep(.el-form-item__label) { color: var(--md-on-surface-variant); padding-bottom: 4px; font-size: 14px; }
:deep(.el-form-item) { margin-bottom: 24px; }
@media (max-width: 480px) { .login-bg { justify-content: flex-start; padding-top: 24px; } .login-body { padding: 8px 20px 24px; } }
</style>




