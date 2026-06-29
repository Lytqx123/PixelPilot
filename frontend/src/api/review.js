import request from './request'

export const reviewApi = {
  getPendingDocuments(params) {
    return request.get('/review/documents/pending', { params })
  },
  approveDocument(id, data) {
    return request.post(`/review/documents/${id}/approve`, data)
  },
  rejectDocument(id, data) {
    return request.post(`/review/documents/${id}/reject`, data)
  },
  getPendingApplications(params) {
    return request.get('/review/applications/pending', { params })
  },
  approveApplication(id, data) {
    return request.post(`/review/applications/${id}/approve`, data)
  },
  rejectApplication(id) {
    return request.post(`/review/applications/${id}/reject`)
  },
  getReviewHistory(params) {
    return request.get('/review/history', { params })
  },
}