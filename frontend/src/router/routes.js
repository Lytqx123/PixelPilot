const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/LoginView.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/views/layout/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/knowledge',
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('@/views/knowledge/QAPage.vue'),
        meta: { title: '智能问答', icon: 'ChatDotRound' },
      },
      {
        path: 'documents',
        name: 'Documents',
        component: () => import('@/views/documents/DocumentList.vue'),
        meta: { title: '文档管理' },
      },
      {
        path: 'documents/upload',
        name: 'DocumentUpload',
        component: () => import('@/views/documents/DocumentUpload.vue'),
        meta: { title: '文件上传' },
      },
      {
        path: 'documents/favorites',
        name: 'Favorites',
        component: () => import('@/views/documents/Favorites.vue'),
        meta: { title: '我的收藏' },
      },
      {
        path: 'documents/download-history',
        name: 'DownloadHistory',
        component: () => import('@/views/documents/DownloadHistory.vue'),
        meta: { title: '下载历史' },
      },
      {
        path: 'admin/users',
        name: 'UserManage',
        component: () => import('@/views/admin/UserManage.vue'),
        meta: { title: '人员管理', role: ['SUPER_ADMIN', 'ADMIN'] },
      },
      {
        path: 'admin/settings',
        name: 'SystemSettings',
        component: () => import('@/views/admin/SystemSettings.vue'),
        meta: { title: '系统设置', role: ['SUPER_ADMIN'] },
      },
      {
        path: 'admin/vector-index',
        name: 'VectorIndex',
        component: () => import('@/views/admin/VectorIndex.vue'),
        meta: { title: '向量索引管理', role: ['SUPER_ADMIN'] },
      },
      {
        path: 'admin/audit',
        name: 'AuditLogs',
        component: () => import('@/views/admin/AuditLogs.vue'),
        meta: { title: '审计日志', role: ['SUPER_ADMIN', 'ADMIN'] },
      },
      {
        path: 'review/documents',
        name: 'DocumentReview',
        component: () => import('@/views/review/DocumentReview.vue'),
        meta: { title: '待审文档', role: ['ADMIN', 'REVIEWER'] },
      },
      {
        path: 'review/applications',
        name: 'ApplicationReview',
        component: () => import('@/views/review/ApplicationReview.vue'),
        meta: { title: '访问申请审批', role: ['ADMIN', 'REVIEWER'] },
      },
      {
        path: 'review/history',
        name: 'ReviewHistory',
        component: () => import('@/views/review/ReviewHistory.vue'),
        meta: { title: '审核历史', role: ['SUPER_ADMIN', 'ADMIN', 'REVIEWER'] },
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/profile/ProfileView.vue'),
        meta: { title: '个人中心' },
      },
    ],
  },
]

export default routes