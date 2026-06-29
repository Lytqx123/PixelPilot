import { useAuthStore } from '@/stores/auth'

// 路由守卫，处理登录和权限校验
export function createAuthGuard(router) {
  router.beforeEach((to, from, next) => {
    const authStore = useAuthStore()

    // 白名单页面直接过
    if (to.meta.requiresAuth === false) {
      next()
      return
    }

    // 没登录跳登录页
    if (!authStore.isLoggedIn) {
      next('/login')
      return
    }

    // 账号被禁用了就强制登出
    if (authStore.user && authStore.user.status === 0) {
      authStore.logout()
      next('/login')
      return
    }

    // 角色权限检查
    if (to.meta.role) {
      const roles = Array.isArray(to.meta.role) ? to.meta.role : [to.meta.role]
      const userRole = authStore.roleCode
      if (roles.includes(userRole)) {
        next()
        return
      }
      next('/knowledge')  // 没权限就回首页
      return
    }

    next()
  })
}
