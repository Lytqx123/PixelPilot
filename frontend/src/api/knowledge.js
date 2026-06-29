import request from './request'

export const knowledgeApi = {
  queryKnowledge(data) {
    return request.post('/knowledge/query', data)
  },

  /**
   * 优化 4: 流式问答（SSE）
   * onText(text) - 收到文本增量时回调
   * onSources(sources) - 收到来源文档列表时回调
   * onDone() - 回答完成时回调
   * onError(msg) - 出错时回调
   * 返回一个 Promise，流式完成时 resolve，出错时 reject
   * data 中可选字段: use_large_model (bool) — 是否使用 14B 大模型（推理更慢，质量更高）
   */
  queryKnowledgeStream(data, callbacks) {
    const { onText, onSources, onDone, onError } = callbacks || {}
    const token = localStorage.getItem('token') || localStorage.getItem('auth_token')
    let fullAnswer = ''
    let sources = []

    // 确保 use_large_model 字段存在并默认 False（兼容旧请求）
    const payload = {
      question: data.question,
      conversation_id: data.conversation_id,
      top_k: data.top_k || 7,
      use_large_model: !!data.use_large_model,
    }

    return new Promise((resolve) => {
      const es = new EventSourcePolyfillWrapper(
        '/api/knowledge/query/stream',
        {
          method: 'POST',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          payload,
        },
      )

      es.onopen = () => {
        // 连接成功
      }

      es.addEventListener('sources', (e) => {
        try {
          const data = JSON.parse(e.data)
          sources = data
          if (onSources) onSources(data)
        } catch { /* 忽略解析错误 */ }
      })

      es.addEventListener('text', (e) => {
        try {
          const text = JSON.parse(e.data)
          fullAnswer += text
          if (onText) onText(text, fullAnswer)
        } catch {
          // 如果不是 JSON，则直接当作字符串
          fullAnswer += e.data
          if (onText) onText(e.data, fullAnswer)
        }
      })

      es.addEventListener('done', () => {
        es.close()
        if (onDone) onDone()
        resolve({ answer: fullAnswer, sources })
      })

      es.addEventListener('error', (e) => {
        try {
          const errData = JSON.parse(e.data)
          if (errData && errData.message) {
            if (onError) onError(errData.message)
          }
        } catch {
          // EventSource 原生错误事件
          if (e && e.message && onError) {
            onError(e.message)
          }
        }
        // 遇到错误也优雅结束
        es.close()
        if (onDone) onDone()
        resolve({ answer: fullAnswer, sources })
      })

      es.onerror = (e) => {
        es.close()
        if (onError) onError('流式连接中断')
        if (onDone) onDone()
        resolve({ answer: fullAnswer, sources })
      }
    })
  },

  exportData(data) {
    return request.post('/data/export', data, {
      responseType: 'blob',
    })
  },
  getConversations() {
    return request.get('/knowledge/conversations')
  },
  createConversation() {
    return request.post('/knowledge/conversations')
  },
  getConversationMessages(convId) {
    return request.get(`/knowledge/conversations/${convId}/messages`)
  },
  deleteConversation(convId) {
    return request.delete(`/knowledge/conversations/${convId}`)
  },
}

/**
 * 简单的 SSE 封装：浏览器原生 EventSource 不支持 POST / 自定义 header，
 * 所以用 fetch + ReadableStream 来模拟 EventSource 的行为。
 */
class EventSourcePolyfillWrapper {
  constructor(url, opts = {}) {
    this.url = url
    this.method = opts.method || 'GET'
    this.headers = opts.headers || {}
    this.payload = opts.payload
    this._listeners = {}
    this._closed = false
    this.onopen = null
    this.onerror = null

    // 启动流式请求
    this._start()
  }

  addEventListener(event, handler) {
    this._listeners[event] = this._listeners[event] || []
    this._listeners[event].push(handler)
  }

  removeEventListener(event, handler) {
    if (this._listeners[event]) {
      this._listeners[event] = this._listeners[event].filter((h) => h !== handler)
    }
  }

  _emit(event, data) {
    const handlers = this._listeners[event]
    if (handlers) {
      for (const h of handlers) {
        try { h(data) } catch { /* 忽略 */ }
      }
    }
  }

  close() {
    this._closed = true
    if (this._abortController) {
      try { this._abortController.abort() } catch { /* 忽略 */ }
    }
  }

  async _start() {
    try {
      const token = localStorage.getItem('token') || localStorage.getItem('auth_token')
      const headers = { 'Content-Type': 'application/json', ...this.headers }
      if (token && !headers.Authorization) {
        headers.Authorization = `Bearer ${token}`
      }

      this._abortController = new AbortController()
      const response = await fetch(this.url, {
        method: this.method,
        headers,
        body: JSON.stringify(this.payload || {}),
        signal: this._abortController.signal,
      })

      if (this.onopen) this.onopen()

      if (!response.ok) {
        this._emit('error', { message: `HTTP ${response.status}` })
        if (this.onerror) this.onerror({ message: `HTTP ${response.status}` })
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''

      while (!this._closed) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        // SSE 协议: 事件以空行分隔
        const events = buffer.split('\n\n')
        // 保留最后一段（可能不完整）到 buffer
        buffer = events.pop()

        for (const eventBlock of events) {
          if (!eventBlock.trim()) continue
          this._parseAndEmit(eventBlock)
        }
      }
    } catch (err) {
      if (this._closed) return
      this._emit('error', { message: err.message || '连接失败' })
      if (this.onerror) this.onerror(err)
    }
  }

  _parseAndEmit(block) {
    // 解析 SSE 行: "event: xxx\ndata: yyy"
    const lines = block.split('\n')
    let eventName = 'text' // 默认事件名
    let dataLines = []

    for (const line of lines) {
      if (line.startsWith('event:')) {
        eventName = line.substring(6).trim()
      } else if (line.startsWith('data:')) {
        dataLines.push(line.substring(5).trim())
      }
    }

    if (dataLines.length > 0) {
      const dataStr = dataLines.join('\n')
      this._emit(eventName, { data: dataStr, type: eventName })
    }
  }
}
