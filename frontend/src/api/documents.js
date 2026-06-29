import request from './request'

export const documentsApi = {
  getDocuments(params) {
    return request.get('/documents', { params })
  },
  getDepartments() {
    return request.get('/documents/departments')
  },
  getDocumentTags() {
    return request.get('/documents/tags')
  },
  getAllDataTags() {
    return request.get('/documents/data-tags')
  },
  uploadDocument(formData) {
    return request.post('/documents/upload', formData)
  },
  applyAccess(id, data) {
    return request.post(`/documents/${id}/apply`, data)
  },
  downloadDocument(id) {
    return request.get(`/documents/${id}/download`, {
      responseType: 'blob',
    })
  },
  downloadByToken(token) {
    return request.get(`/documents/download-by-token/${token}`, {
      responseType: 'blob',
    })
  },
  viewDocument(id) {
    return request.get(`/documents/${id}/view`, {
      responseType: 'blob',
    })
  },
  deleteDocument(id) {
    return request.delete(`/documents/${id}`)
  },
  updateDocumentTags(id, data) {
    return request.put(`/documents/${id}/tags`, data)
  },
  setAccessMode(id, data) {
    return request.put(`/documents/${id}/access-mode`, data)
  },
  addFavorite(documentId) {
    return request.post('/documents/favorites', { document_id: documentId })
  },
  removeFavorite(documentId) {
    return request.delete(`/documents/favorites/${documentId}`)
  },
  getFavorites(params) {
    return request.get('/documents/favorites', { params })
  },
  getDownloadHistory(params) {
    return request.get('/documents/download-history', { params })
  },
  getViewDocumentUrl(id) {
    const token = localStorage.getItem('token')
    const base = `${window.location.origin}/api/documents/${id}/view`
    return token ? `${base}?token=${encodeURIComponent(token)}` : base
  },
}
