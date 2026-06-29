import request from './request'

export const adminApi = {
  getUsers(params) {
    return request.get('/admin/users', { params })
  },
  getUserDetail(userId) {
    return request.get(`/admin/users/${userId}/detail`)
  },
  createUser(data) {
    return request.post('/admin/users', data)
  },
  updateUser(id, data) {
    return request.put(`/admin/users/${id}`, data)
  },
  disableUser(id) {
    return request.put(`/admin/users/${id}/disable`)
  },
  deleteUser(id) {
    return request.delete(`/admin/users/${id}`)
  },
  getAvailableRoles() {
    return request.get('/admin/available-roles')
  },
  getSystemTags() {
    return request.get('/admin/tags')
  },
  getTagsList(tagType) {
    return request.get('/admin/tags/list', { params: { tag_type: tagType } })
  },
  createTag(data) {
    return request.post('/admin/tags', data)
  },
  updateTag(id, data) {
    return request.put(`/admin/tags/${id}`, data)
  },
  deleteTag(id) {
    return request.delete(`/admin/tags/${id}`)
  },
  getAuditLogs(params) {
    return request.get('/admin/audit/logs', { params })
  },
  exportAuditLogs(params) {
    return request.get('/admin/audit/logs/export', {
      params,
      responseType: 'blob',
    })
  },
  revokeDocumentPermission(documentId, userId) {
    return request.delete(`/admin/documents/${documentId}/revoke/${userId}`)
  },
  batchGrant(data) {
    return request.post('/admin/documents/batch-grant', data)
  },
  previewBatchGrant(data) {
    return request.post('/admin/documents/batch-grant/preview', data)
  },
  getGrantableRoles() {
    return request.get('/admin/documents/grantable-roles')
  },
  getPendingCount() {
    return request.get('/admin/pending-count')
  },
  getReviewers() {
    return request.get('/admin/reviewers')
  },

  // 角色管理（仅超级管理员）
  getRoles() {
    return request.get('/admin/roles')
  },
  createRole(data) {
    return request.post('/admin/roles', data)
  },
  updateRole(id, data) {
    return request.put(`/admin/roles/${id}`, data)
  },
  deleteRole(id) {
    return request.delete(`/admin/roles/${id}`)
  },

  // 部门管理（仅超级管理员）
  getDepartments() {
    return request.get('/admin/departments')
  },
  createDepartment(data) {
    return request.post('/admin/departments', data)
  },
  updateDepartment(id, data) {
    return request.put(`/admin/departments/${id}`, data)
  },
  deleteDepartment(id) {
    return request.delete(`/admin/departments/${id}`)
  },

  // 系统配置管理（仅超级管理员）
  getSystemConfigs() {
    return request.get('/admin/system-configs')
  },
  updateSystemConfig(key, data) {
    return request.put(`/admin/system-configs/${key}`, data)
  },

  // 数据标签分类管理（新）
  getDataTagCategories() {
    return request.get('/admin/data-tag-categories')
  },
  getAllDataTagsGrouped() {
    return request.get('/admin/data-tag-categories/all-tags')
  },
  getDataTagCategoryDetail(id) {
    return request.get(`/admin/data-tag-categories/${id}`)
  },
  createDataTagCategory(data) {
    return request.post('/admin/data-tag-categories', data)
  },
  updateDataTagCategory(id, data) {
    return request.put(`/admin/data-tag-categories/${id}`, data)
  },
  deleteDataTagCategory(id) {
    return request.delete(`/admin/data-tag-categories/${id}`)
  },

  // 数据标签值管理（新）
  getDataTags(params) {
    return request.get('/admin/data-tags', { params })
  },
  createDataTag(data) {
    return request.post('/admin/data-tags', data)
  },
  updateDataTag(id, data) {
    return request.put(`/admin/data-tags/${id}`, data)
  },
  deleteDataTag(id) {
    return request.delete(`/admin/data-tags/${id}`)
  },

  // 向量索引管理（仅超级管理员）
  getVectorIndexStatus() {
    return request.get('/admin/vector-index/status')
  },
  rebuildAllVectorIndex() {
    return request.post('/admin/vector-index/rebuild-all')
  },
  rebuildSingleDocumentVector(documentId) {
    return request.post(`/admin/vector-index/rebuild/${documentId}`)
  },
  cleanupOrphanVectors() {
    return request.post('/admin/vector-index/cleanup-orphans')
  },
}
