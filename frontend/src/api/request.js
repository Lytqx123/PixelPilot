import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 请求拦截：自动带token
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截：统一错误处理
request.interceptors.response.use(
  (response) => {
    // blob下载要特殊处理，后端返回错误时可能是json不是blob
    if (response.config.responseType === 'blob') {
      const contentType = response.headers['content-type'] || ''
      if (contentType.includes('application/json') && response.data instanceof Blob) {
        return response.data.text().then(text => {
          const errData = JSON.parse(text)
          ElMessage.error(errData.detail || '请求失败')
          return Promise.reject(new Error(errData.detail || '请求失败'))
        })
      }
      return response.data
    }
    return response.data
  },
  async (error) => {
    const status = error.response?.status
    const requestUrl = error.config?.url || ''
    let detail = '请求失败'
    let extraData = {}

    // blob类型的错误要先转成json读
    if (error.response?.data instanceof Blob) {
      try {
        const text = await error.response.data.text()
        const parsed = JSON.parse(text)
        detail = parsed.detail || parsed.message || '请求失败'
        extraData = parsed || {}
      } catch {
        detail = '请求失败'
      }
    } else {
      detail = error.response?.data?.detail || error.response?.data?.message || '请求失败'
      extraData = error.response?.data || {}
    }

    const method = (error.config?.method || '').toUpperCase()

    if (status === 401) {
      // 登录接口401是密码错，别跳走
      if (requestUrl.includes('/auth/login')) {
        const loginMsg = extraData.message || extraData.detail || '账号或密码错误'
        ElMessage.error(loginMsg)
        return Promise.reject(error)
      }
      // 其他接口401清缓存跳登录
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      const currentPath = window.location.hash?.replace('#', '') || window.location.pathname
      if (!currentPath.includes('/login')) {
        window.location.href = '/login'
      }
      ElMessage.error('登录已过期，请重新登录')
    } else if (status === 403) {
      // 文档无权限时弹申请窗口
      const action = extraData.action
      const documentId = extraData.document_id
      const documentName = extraData.document_name || ''

      if (action === 'apply' && documentId) {
        window.dispatchEvent(new CustomEvent('pixelpulse:403-apply', {
          detail: {
            document_id: documentId,
            document_name: documentName,
            message: typeof detail === 'string' ? detail : '无权访问此文档',
          },
        }))
        ElMessage({
          message: `无权访问「${documentName || '该文档'}」，请申请访问权限`,
          type: 'warning',
          duration: 5000,
        })
        return Promise.reject(error)
      }
      ElMessage.error(typeof detail === 'string' ? detail : '权限不足')
    } else if (status === 404) {
      ElMessage.error(typeof detail === 'string' ? detail : '资源不存在')
    } else if (status === 400) {
      ElMessage.warning(typeof detail === 'string' ? detail : '请求参数错误')
    } else if (status >= 500) {
      // GET请求静默错误，写操作才弹错，减少打扰
      if (method === 'POST' || method === 'PUT' || method === 'DELETE') {
        const msg500 = typeof detail === 'string' && detail !== '请求失败' ? detail : '服务器内部错误，请稍后重试'
        ElMessage.error(msg500)
      } else {
        console.error(`[Server Error ${status}] ${method} ${requestUrl}:`, detail)
      }
    } else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      ElMessage.error('请求超时，请检查网络连接后重试')
    } else if (error.message?.includes('Network Error') || !status) {
      ElMessage.error('网络连接失败，请检查后端服务是否正常运行')
    } else {
      console.error(`[Request Error] ${status || 'UNKNOWN'} ${requestUrl}:`, detail)
      ElMessage.error(typeof detail === 'string' ? detail : '请求失败，请稍后重试')
    }

    return Promise.reject(error)
  }
)

export default request