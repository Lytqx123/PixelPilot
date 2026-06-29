import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(null)
  const menus = ref([])

  const isLoggedIn = computed(() => !!token.value)
  const roleCode = computed(() => user.value?.role_code || '')
  const roleName = computed(() => user.value?.role_name || '')
  const realName = computed(() => user.value?.real_name || '')
  const isAdmin = computed(() => roleCode.value === 'SUPER_ADMIN' || roleCode.value === 'ADMIN')
  const isSuperAdmin = computed(() => roleCode.value === 'SUPER_ADMIN')
  const isReviewer = computed(() => roleCode.value === 'REVIEWER' || roleCode.value === 'ADMIN' || roleCode.value === 'SUPER_ADMIN')

  function setAuth(data) {
    const info = data.user_info || {}
    token.value = data.access_token
      user.value = {
        id: info.id,
        username: info.username,
        real_name: info.real_name,
        gender: info.gender || '',
        phone: info.phone || '',
        personal_description: info.personal_description || '',
        role_code: info.role_code,
        role_name: info.role_name,
        department_id: info.department_id ?? null,
        department_name: info.department_name || '',
        status: info.status ?? 1,
      }
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('user', JSON.stringify(user.value))
  }

  function clearAuth() {
    token.value = ''
    user.value = null
    menus.value = []
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  async function login(username, password) {
    // 清除旧的 auth 状态（不影响其他业务域的 localStorage 数据）
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    token.value = ''
    user.value = null
    menus.value = []
    const res = await authApi.login(username, password)
    setAuth(res)
    return res
  }

  async function fetchUserInfo() {
    try {
      const res = await authApi.getCurrentUser()
      // 后端返回的 status=0 表示用户已被禁用，应立即登出
      if (res.status === 0) {
        clearAuth()
        window.location.href = '/login'
        return
      }
      user.value = {
        id: res.id,
        username: res.username,
        real_name: res.real_name,
        gender: res.gender || '',
        phone: res.phone || '',
        personal_description: res.personal_description || '',
        role_code: res.role_code,
        role_name: res.role_name,
        department_id: res.department_id ?? null,
        department_name: res.department_name || '',
        status: res.status ?? 1,
      }
      localStorage.setItem('user', JSON.stringify(user.value))
    } catch (e) {
      // 获取用户信息失败（如 token 失效）时清除本地状态，避免使用过期角色信息
      if (e?.response?.status === 401) {
        clearAuth()
      }
    }
  }

  async function fetchMenus() {
    try {
      const res = await authApi.getMenus()
      menus.value = res.menus || []
    } catch (e) {
      // ignore
    }
  }

  function logout() {
    clearAuth()
    // 使用 window.location 跳转,避免在 store 中依赖 useRouter()(后者需要组件 setup 上下文)
    window.location.href = '/login'
  }

  // 从 localStorage 恢复 user
  function restoreFromStorage() {
    if (token.value) {
      const saved = localStorage.getItem('user')
      if (saved) {
        try {
          user.value = JSON.parse(saved)
        } catch {
          // ignore
        }
      }
    }
  }

  restoreFromStorage()

  return {
    token, user, menus,
    isLoggedIn, roleCode, roleName, realName, isAdmin, isSuperAdmin, isReviewer,
    login, logout, fetchUserInfo, fetchMenus, clearAuth,
  }
})