<template>
  <div class="layout-wrapper">
    <!-- 左侧:侧边栏 -->
    <aside class="sidebar" :class="{ collapsed: appStore.sidebarCollapsed }">
      <!-- Logo 区 -->
      <div class="sidebar-logo">
        <div class="logo-icon">
          <el-icon :size="26" color="#ffffff"><Cpu /></el-icon>
        </div>
        <transition name="fade">
          <span v-show="!appStore.sidebarCollapsed" class="logo-text">
            Pixel<span class="logo-accent">Pulse</span>
          </span>
        </transition>
      </div>

      <!-- 导航区(分组) -->
      <nav class="sidebar-nav">
        <template v-for="group in navGroups" :key="group.title">
          <div v-if="group.items.length > 0" class="nav-group">
            <div v-show="!appStore.sidebarCollapsed" class="nav-group-title">{{ group.title }}</div>
            <router-link
              v-for="item in group.items"
              :key="item.path"
              :to="item.path"
              class="nav-item"
              :class="{ active: isItemActive(item.path) }"
            >
              <el-icon :size="19"><component :is="item.icon" /></el-icon>
              <span v-show="!appStore.sidebarCollapsed" class="nav-label">{{ item.label }}</span>
              <el-badge
                v-if="item.badge !== undefined && item.badge > 0"
                :value="item.badge"
                :max="99"
                class="nav-badge"
              />
            </router-link>
          </div>
        </template>
      </nav>

      <!-- 折叠按钮 -->
      <div class="sidebar-footer">
        <el-icon class="collapse-icon" @click="appStore.toggleSidebar">
          <DArrowLeft v-if="!appStore.sidebarCollapsed" />
          <DArrowRight v-else />
        </el-icon>
      </div>
    </aside>

    <!-- 右侧:主内容区 -->
    <div class="main-area">
      <header class="topbar">
        <div class="topbar-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/knowledge' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="route.meta.title">{{ route.meta.title }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="topbar-right">
          <!-- 待办申请通知铃铛 -->
          <div
            v-if="authStore.isReviewer"
            class="notification-bell"
            :class="{ 'has-pending': pendingCount > 0 }"
            @click="$router.push('/review/applications')"
            title="待处理访问申请"
          >
            <el-badge :value="pendingCount" :hidden="pendingCount === 0" :max="99" class="bell-badge">
              <el-icon :size="20"><Bell /></el-icon>
            </el-badge>
          </div>
          <el-dropdown trigger="click">
            <div class="user-tag">
              <el-avatar :size="32" class="user-avatar">
                {{ (authStore.realName || authStore.user?.username || 'U').charAt(0).toUpperCase() }}
              </el-avatar>
              <span class="user-name">{{ authStore.realName || authStore.user?.username || '用户' }}</span>
              <el-tag size="small" effect="plain" round>{{ authStore.roleName }}</el-tag>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>
                  账号:{{ authStore.user?.username }}
                </el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">
                  <el-icon><SwitchButton /></el-icon> 退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main class="content">
        <router-view />
      </main>
    </div>

    <!-- 全局申请访问对话框 -->
    <el-dialog v-model="applyDialogVisible" title="申请文档访问权限" width="500px">
      <el-form :model="applyForm" label-width="100px">
        <el-form-item label="选择审核员">
          <el-select
            v-model="applyForm.reviewer_ids"
            multiple
            filterable
            placeholder="请选择至少一名审核员/管理员"
            style="width: 100%"
          >
            <el-option
              v-for="r in reviewers"
              :key="r.id"
              :label="`${r.real_name || r.username} (${r.role_name})`"
              :value="r.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="申请原因">
          <el-input
            v-model="applyForm.reason"
            type="textarea"
            :rows="3"
            placeholder="请说明申请访问该文档的原因"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="applyDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="applying" @click="submitApply">提交申请</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { Cpu, DArrowLeft, DArrowRight, SwitchButton, Bell } from '@element-plus/icons-vue'
import {
  ChatDotRound, Document, Upload, UserFilled, Setting,
  Clock, Checked, Tickets, DataAnalysis,
  Star, Download,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { documentsApi } from '@/api/documents'
import { adminApi } from '@/api/admin'

const route = useRoute()
const authStore = useAuthStore()
const appStore = useAppStore()

const pendingDocuments = ref(0)
const pendingApplications = ref(0)
let pollTimer = null

async function pollPendingCount() {
  if (!authStore.isReviewer) return
  try {
    const res = await adminApi.getPendingCount()
    pendingDocuments.value = (res && typeof res.pending_documents === 'number') ? res.pending_documents : 0
    pendingApplications.value = (res && typeof res.pending_applications === 'number') ? res.pending_applications : 0
  } catch {
    // ignore
  }
}

const pendingCount = computed(() => pendingDocuments.value + pendingApplications.value)

// 侧边栏分组结构
const navGroups = computed(() => [
  {
    title: '工作台',
    items: [
      { path: '/knowledge', label: '智能问答', icon: ChatDotRound },
    ],
  },
  {
    title: '文档中心',
    items: [
      { path: '/documents', label: '文档管理', icon: Document },
      { path: '/documents/upload', label: '文件上传', icon: Upload },
      { path: '/documents/favorites', label: '我的收藏', icon: Star },
      { path: '/documents/download-history', label: '下载历史', icon: Download },
    ],
  },
  {
    title: '审核中心',
    items: (() => {
      const role = authStore.roleCode
      const items = []
      // 待审文档 / 访问申请：仅部门管理员与审核员参与具体审核
      if (role === 'ADMIN' || role === 'REVIEWER') {
        items.push({ path: '/review/documents', label: '待审文档', icon: Checked, badge: pendingDocuments.value })
        items.push({ path: '/review/applications', label: '访问申请', icon: Tickets, badge: pendingApplications.value })
      }
      // 审核历史：超级管理员看全部，部门管理员/审核员看本部门
      if (role === 'SUPER_ADMIN' || role === 'ADMIN' || role === 'REVIEWER') {
        items.push({ path: '/review/history', label: '审核历史', icon: Clock })
      }
      return items
    })(),
  },
  {
    title: '系统管理',
    items: authStore.isSuperAdmin ? [
      { path: '/admin/users', label: '人员管理', icon: UserFilled },
      { path: '/admin/settings', label: '系统设置', icon: Setting },
      { path: '/admin/audit', label: '审计日志', icon: DataAnalysis },
    ] : (authStore.roleCode === 'ADMIN' ? [
      { path: '/admin/users', label: '人员管理', icon: UserFilled },
      { path: '/admin/audit', label: '审计日志', icon: DataAnalysis },
    ] : []),
  },
  {
    title: '个人',
    items: [
      { path: '/profile', label: '个人中心', icon: UserFilled },
    ],
  },
])

function isItemActive(path) {
  // 文档相关路由高亮 /documents
  if (path === '/documents' && route.path.startsWith('/documents')) {
    return route.path === '/documents'
  }
  return route.path === path
}

function handleLogout() {
  authStore.logout()
}

// 全局申请访问对话框
const applyDialogVisible = ref(false)
const applyForm = reactive({ document_id: null, reason: '', reviewer_ids: [] })
const reviewers = ref([])
const applying = ref(false)

onMounted(() => {
  window.addEventListener('pixelpulse:403-apply', handle403ApplyEvent)
  // 审核员/管理员:每30秒轮询待处理申请数
  if (authStore.isReviewer) {
    pollPendingCount()
    pollTimer = setInterval(pollPendingCount, 30000)
  }
})
onUnmounted(() => {
  window.removeEventListener('pixelpulse:403-apply', handle403ApplyEvent)
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})

async function handle403ApplyEvent(e) {
  const { document_id, document_name } = e.detail || {}
  if (document_id) {
    applyForm.document_id = document_id
    applyForm.reason = `通过"${document_name || '文档'}"的访问权限提示发起申请`
    applyForm.reviewer_ids = []
    await fetchReviewers()
    applyDialogVisible.value = true
  }
}

async function fetchReviewers() {
  try {
    const res = await adminApi.getReviewers()
    reviewers.value = res.items || []
  } catch {
    reviewers.value = []
  }
}

async function submitApply() {
  if (!applyForm.reason.trim()) {
    ElMessage.warning('请填写申请原因')
    return
  }
  if (!applyForm.reviewer_ids || applyForm.reviewer_ids.length === 0) {
    ElMessage.warning('请至少选择一名审核员/管理员')
    return
  }
  applying.value = true
  try {
    await documentsApi.applyAccess(applyForm.document_id, {
      reason: applyForm.reason,
      reviewer_ids: applyForm.reviewer_ids
    })
    ElMessage.success('申请已提交，等待审核')
    applyDialogVisible.value = false
  } catch {
    // handled by interceptor
  } finally {
    applying.value = false
  }
}
</script>

<style scoped>
.layout-wrapper {
  display: flex;
  height: 100vh;
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  font-family: 'Segoe UI', 'PingFang SC', 'Inter', sans-serif;
}

/* === Sidebar === */
.sidebar {
  width: 240px;
  background: #ffffff;
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  transition: width 0.28s cubic-bezier(0.4, 0, 0.2, 1);
  flex-shrink: 0;
  box-shadow: 2px 0 12px rgba(15, 23, 42, 0.04);
  z-index: 10;
}

.sidebar.collapsed {
  width: 72px;
}

/* Logo 区 */
.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 20px;
  border-bottom: 1px solid var(--color-border-light);
  height: 64px;
}

.logo-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  background: var(--color-primary-gradient);
  border-radius: 11px;
  box-shadow: 0 4px 12px rgba(14, 165, 233, 0.3);
}

.logo-text {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text-primary);
  white-space: nowrap;
  letter-spacing: 0.2px;
}

.logo-accent {
  color: var(--color-primary);
}

/* 导航区 */
.sidebar-nav {
  flex: 1;
  padding: 12px 10px;
  overflow-y: auto;
  overflow-x: hidden;
}

.nav-group {
  margin-bottom: 6px;
}

.nav-group-title {
  padding: 14px 14px 6px;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-placeholder);
  letter-spacing: 1px;
  text-transform: uppercase;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.18s ease;
  white-space: nowrap;
  position: relative;
  margin-bottom: 2px;
}

.nav-item:hover {
  background: var(--color-bg-hover);
  color: var(--color-primary);
}

.nav-item.active {
  background: var(--color-primary-light);
  color: var(--color-primary-hover);
  font-weight: 600;
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: -10px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: var(--color-primary);
  border-radius: 0 3px 3px 0;
}

.nav-label {
  font-weight: 500;
  flex: 1;
}

.nav-badge {
  margin-left: auto;
}

/* 折叠态:隐藏分组标题,居中图标 */
.sidebar.collapsed .nav-item {
  justify-content: center;
  padding: 10px;
}

.sidebar.collapsed .nav-badge {
  position: absolute;
  top: 2px;
  right: 2px;
  margin-left: 0;
}

/* 折叠按钮 */
.sidebar-footer {
  padding: 12px 18px;
  border-top: 1px solid var(--color-border-light);
  display: flex;
  justify-content: center;
}

.collapse-icon {
  cursor: pointer;
  color: var(--color-text-placeholder);
  font-size: 18px;
  padding: 6px;
  border-radius: var(--radius-sm);
  transition: all 0.2s;
}

.collapse-icon:hover {
  background: var(--color-bg-hover);
  color: var(--color-primary);
}

/* === Main Area === */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  height: 60px;
  background: #ffffff;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.02);
}

.topbar-left {
  display: flex;
  align-items: center;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.notification-bell {
  cursor: pointer;
  padding: 8px;
  border-radius: var(--radius-md);
  transition: all 0.2s;
  display: flex;
  align-items: center;
  color: var(--color-text-placeholder);
}

.notification-bell:hover {
  background: var(--color-primary-lighter);
  color: var(--color-primary);
}

.notification-bell.has-pending {
  color: var(--color-danger);
  animation: bellShake 1.5s ease-in-out infinite;
}

@keyframes bellShake {
  0%, 100% { transform: rotate(0); }
  20% { transform: rotate(-8deg); }
  40% { transform: rotate(8deg); }
  60% { transform: rotate(-4deg); }
  80% { transform: rotate(4deg); }
}

.bell-badge {
  display: flex;
  align-items: center;
}

.user-tag {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  padding: 4px 12px;
  border-radius: var(--radius-md);
  transition: background 0.2s;
}

.user-tag:hover {
  background: var(--color-bg-hover);
}

.user-avatar {
  background: var(--color-primary-gradient);
  color: #ffffff;
  font-weight: 600;
  font-size: 14px;
  box-shadow: 0 2px 6px rgba(14, 165, 233, 0.25);
}

.user-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
}

.content {
  flex: 1;
  padding: 20px 24px;
  overflow-y: auto;
  background: var(--color-bg-page);
}

/* 过渡动画 */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

/* Override element-plus breadcrumb */
:deep(.el-breadcrumb__inner) {
  color: var(--color-text-secondary);
}

:deep(.el-breadcrumb__inner.is-link:hover) {
  color: var(--color-primary-hover);
}

:deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) {
  color: var(--color-text-primary);
  font-weight: 500;
}
</style>
