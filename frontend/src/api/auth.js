import request from './request'

export const authApi = {
  login(username, password) {
    return request.post('/auth/login', { username, password })
  },
  getCurrentUser() {
    return request.get('/auth/me')
  },
  getMenus() {
    return request.get('/auth/menus')
  },
  changePassword(data) {
    return request.put('/auth/change-password', data)
  },
  updatePhone(data) {
    return request.put('/auth/update-phone', data)
  },
  updateDescription(data) {
    return request.put('/auth/update-description', data)
  },
}
