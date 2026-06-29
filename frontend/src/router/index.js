import { createRouter, createWebHistory } from 'vue-router'
import routes from './routes'
import { createAuthGuard } from './guards'

const router = createRouter({
  history: createWebHistory(),
  routes,
})

createAuthGuard(router)

export default router