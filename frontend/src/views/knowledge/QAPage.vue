<template>
  <div class="qa-wrapper">
    <!-- 左侧:对话历史 -->
    <aside class="qa-history">
      <div class="history-header">
        <div class="history-title-row">
          <el-icon :size="18" color="var(--color-primary)"><ChatLineSquare /></el-icon>
          <span>对话历史</span>
        </div>
        <el-button
          type="primary"
          size="small"
          :loading="convLoading"
          :icon="Plus"
          round
          @click="handleNewConversation"
        >
          新建
        </el-button>
      </div>
      <div class="history-list" v-if="conversations.length > 0">
        <div
          v-for="conv in conversations"
          :key="conv.id"
          class="history-item"
          :class="{ active: activeConvId === conv.id }"
          @click="switchConversation(conv.id)"
        >
          <div class="history-left">
            <span class="history-title">{{ conv.title || '新对话' }}</span>
            <span class="history-time">{{ conv.time }}</span>
          </div>
          <el-button
            text
            size="small"
            class="history-delete"
            @click.stop="handleDeleteConversation(conv.id)"
          >
            <el-icon><Close /></el-icon>
          </el-button>
        </div>
      </div>
      <div v-else class="history-empty">
        <el-icon :size="32" color="var(--color-text-disabled)"><ChatLineSquare /></el-icon>
        <span>暂无对话历史</span>
      </div>
    </aside>

    <!-- 中间:对话主体 -->
    <section class="qa-chat">
      <!-- 欢迎页 -->
      <div v-if="currentMessages.length === 0" class="chat-welcome">
        <div class="welcome-icon">
          <div class="welcome-pulse">
            <el-icon :size="52" color="#ffffff"><Cpu /></el-icon>
          </div>
        </div>
        <h2 class="welcome-title">你好,我是PixelPulse AI智能助手小妤</h2>
        <p class="welcome-desc">基于企业知识库为您提供专业的技术支持与知识服务</p>
        <div class="quick-prompts">
          <div
            v-for="prompt in quickPrompts"
            :key="prompt"
            class="prompt-card"
            @click="sendMessage(prompt)"
          >
            <el-icon :size="16" color="var(--color-primary)"><Lightning /></el-icon>
            <span>{{ prompt }}</span>
          </div>
        </div>
      </div>

      <!-- 对话消息 -->
      <div v-else class="chat-messages" ref="msgContainer">
        <div v-for="(msg, idx) in currentMessages" :key="idx" class="msg-group">
          <!-- 用户消息 -->
          <div v-if="msg.question" class="msg-row msg-user">
            <div class="msg-bubble user-bubble">{{ msg.question }}</div>
            <div class="msg-avatar user-avatar">
              <el-icon :size="18" color="#ffffff"><User /></el-icon>
            </div>
          </div>
          <!-- AI 消息 -->
          <div class="msg-row msg-ai">
            <div class="msg-avatar ai-avatar">
              <span class="avatar-text">AI</span>
            </div>
            <div class="msg-bubble ai-bubble">
              <div v-if="msg.loading && !msg.answer" class="thinking-dots">
                <span></span><span></span><span></span>
                <span class="thinking-text">正在思考...</span>
              </div>
              <div v-else class="answer-md" v-html="renderMarkdown(msg.answer)"></div>
              <div v-if="msg.sources && msg.sources.length > 0 && !msg.loading" class="source-refs">
                <div class="source-label clickable" @click="openSourceDialog(msg.sources)">
                  <el-icon :size="14"><Link /></el-icon>
                  <span>相关文件 (共 {{ msg.sources.length }} 个)</span>
                  <el-icon :size="12" class="source-arrow"><ArrowRight /></el-icon>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入栏 -->
      <div class="chat-input-bar">
        <div v-if="currentMessages.length === 1 && !currentMessages[0].question" class="quick-prompts-inline">
          <div
            v-for="prompt in quickPrompts"
            :key="prompt"
            class="prompt-card-mini"
            @click="sendMessage(prompt)"
          >
            <el-icon :size="14" color="var(--color-primary)"><Lightning /></el-icon>
            <span>{{ prompt }}</span>
          </div>
        </div>
        <div class="input-wrapper">
          <el-input
            v-model="inputText"
            placeholder="输入问题,Enter 发送,Shift+Enter 换行"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 4 }"
            class="chat-textarea"
            @keydown.enter.exact.prevent="sendMessage(inputText)"
          />
          <div class="input-actions">
            <span class="char-hint" v-if="inputText.length > 0">{{ inputText.length }}/2000</span>
            <el-button
              type="primary"
              :icon="Promotion"
              :loading="sending"
              :disabled="!inputText.trim()"
              circle
              size="large"
              @click="sendMessage(inputText)"
            />
          </div>
        </div>
      </div>
    </section>

    <!-- 浮动操作按钮 -->
    <div class="qa-quick-actions" v-if="currentMessages.length > 0">
      <el-tooltip content="导出对话" placement="left">
        <el-button circle :icon="Download" size="small" :loading="exporting" @click="handleExport" />
      </el-tooltip>
    </div>

    <el-dialog v-model="applyDialogVisible" title="申请文档访问权限" width="500px">
      <el-form label-width="100px">
        <el-alert
          type="info"
          :closable="false"
          title="申请将自动推送到您所在部门的管理员和审核员进行审批"
          style="margin-bottom: 16px"
        />
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
        <el-form-item label="期望时长">
          <el-select v-model="applyForm.expected_hours" placeholder="请选择期望授权时长" style="width: 100%">
            <el-option label="4 小时" :value="4" />
            <el-option label="8 小时" :value="8" />
            <el-option label="24 小时（1天）" :value="24" />
            <el-option label="72 小时（3天）" :value="72" />
            <el-option label="168 小时（7天）" :value="168" />
            <el-option label="永久（由审核员决定）" :value="0" />
          </el-select>
        </el-form-item>
        <el-form-item label="申请原因">
          <el-input
            v-model="applyForm.reason"
            type="textarea"
            :rows="3"
            placeholder="请说明申请访问原因"
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

    <!-- 相关文件弹窗 -->
    <el-dialog v-model="sourceDialogVisible" title="相关参考文件" width="680px" top="5vh" :close-on-click-modal="false">
      <div class="source-dialog-body">
        <SourceCard
          v-for="src in sortedDialogSources"
          :key="src.document_id"
          :source="src"
          @apply="handleApply"
          @view="handleViewDocument"
          @download="handleDownloadDocument"
          @favorite="(docId) => handleToggleFavorite(docId)"
        />
      </div>
      <template #footer>
        <el-button @click="sourceDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { knowledgeApi } from '@/api/knowledge'
import { documentsApi } from '@/api/documents'
import { adminApi } from '@/api/admin'
import { useAuthStore } from '@/stores/auth'
import SourceCard from '@/components/SourceCard.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatLineSquare, Plus, Cpu, Lightning, Promotion, Download, Close, User, Link, ArrowRight } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({ breaks: true, linkify: true, html: true })
const authStore = useAuthStore()

const msgContainer = ref(null)
const inputText = ref('')
const sending = ref(false)
const exporting = ref(false)
const applying = ref(false)
const applyDialogVisible = ref(false)
const convLoading = ref(false)

const conversations = ref([])
const activeConvId = ref(null)
const currentMessages = ref([])
const applyForm = ref({ document_id: null, reason: '', reviewer_ids: [], expected_hours: 24 })
const sourceDialogVisible = ref(false)
const sortedDialogSources = ref([])
const reviewers = ref([])

// 注意:403 全局事件由 MainLayout 统一处理,此处不再重复监听
// QAPage 的申请对话框仅通过 SourceCard 的 @apply 事件触发

async function fetchReviewers() {
  try {
    const res = await adminApi.getReviewers()
    reviewers.value = res.items || []
  } catch {
    reviewers.value = []
  }
}

const quickPrompts = [
  '如何上传文档到知识库？',
  '文档审核流程是怎样的？',
  '如何申请文档访问权限？',
  '知识库支持哪些文档格式？',
  '如何使用数据标签管理文档？',
]

const welcomeMessages = [
  '👋 你好，我是PixelPulse AI智能助手小妤，请问有什么可以帮助到您？今天想查询什么资料呢？😊',
  '🤖 您好，我是PixelPulse AI智能助手小妤～ 企业知识库中的任何问题都可以问我，例如文档检索、数据查询、规范解读等 😄',
  '✨ Hi，小妤已上线！需要帮您检索最新的业务报告，还是想了解某个流程的操作规范？😎',
  '🌟 欢迎回来！我是PixelPulse AI智能助手小妤，今天需要查询什么？业务文档、技术资料、还是规章制度？🥰',
  '📊 你好呀，我是智能助手小妤！想问一下项目进度，还是想查某个业务的统计数据？随时问我～ 😃',
  '🔍 您好，我是小妤。无论是文档资料、数据报表还是规范文件，我都能帮您快速定位 💪',
  '📋 PixelPulse AI智能助手小妤为您服务！需要帮您汇总相关资料吗？或者检索特定主题下的文档内容？🌟',
  '💡 Hi，我是小妤～ 企业知识库中的各类内容，从技术文档到业务流程，我都能帮您检索 ☺️',
  '🎯 你好，小妤在呢！今天想聊什么？文档查询、资料汇总、还是问题解答？😊',
  '⚡ 您好，我是PixelPulse AI智能助手小妤。需要帮您快速定位某个文档吗？直接告诉我关键词或问题就好 🎉',
  '🛡️ 小妤已就位！今天有什么问题需要解答？资料查找、数据整理、规范查询都可以 😄',
  '📈 Hi there，我是PixelPulse AI智能助手小妤！无论是想查历史文档，还是了解最新规章制度，我都能帮上忙 💪',
]

function randomWelcome() {
  return welcomeMessages[Math.floor(Math.random() * welcomeMessages.length)]
}

onMounted(async () => { await loadConversations() })

async function loadConversations() {
  try {
    const res = await knowledgeApi.getConversations()
    conversations.value = (res.items || []).map(c => ({ ...c, time: formatTimeShort(c.updated_at || c.created_at) }))
    // 有历史对话：自动选中第一个并加载其消息（避免刷新/切换路由后显示空白）
    if (conversations.value.length > 0) {
      const firstConv = conversations.value[0]
      activeConvId.value = firstConv.id
      await loadMessages(firstConv.id)
    } else {
      activeConvId.value = null
      currentMessages.value = []
    }
  } catch { /* handled */ }
}

async function handleDeleteConversation(convId) {
  try {
    await ElMessageBox.confirm('确定要删除此对话吗？此操作不可恢复。', '确认删除', { type: 'warning' })
    await knowledgeApi.deleteConversation(convId)
    conversations.value = conversations.value.filter(c => c.id !== convId)
    if (activeConvId.value === convId) {
      activeConvId.value = null; currentMessages.value = []
      if (conversations.value.length > 0) { activeConvId.value = conversations.value[0].id; await loadMessages(activeConvId.value) }
    }
    ElMessage.success('对话已删除')
  } catch (_e) { /* cancelled */ }
}

async function loadMessages(convId) {
  try {
    const res = await knowledgeApi.getConversationMessages(convId)
    currentMessages.value = (res.items || []).map(m => ({ question: m.question, answer: m.answer, sources: m.sources || [], loading: false }))
    await scrollToBottom()
  } catch { currentMessages.value = [] }
}

async function handleNewConversation() {
  convLoading.value = true
  try {
    const res = await knowledgeApi.createConversation()
    conversations.value.unshift({ id: res.id, title: '新对话', time: new Date().toLocaleString() })
    activeConvId.value = res.id
    currentMessages.value = [{
      question: '',
      answer: randomWelcome(),
      sources: [],
      loading: false,
    }]
  } catch { ElMessage.error('创建对话失败') } finally { convLoading.value = false }
}

async function switchConversation(convId) { activeConvId.value = convId; await loadMessages(convId) }

function renderMarkdown(text) { return text ? md.render(text) : '' }
function formatTimeShort(isoStr) { if (!isoStr) return ''; try { const d = new Date(isoStr); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}` } catch { return isoStr } }

function openSourceDialog(sources) {
  if (!sources || !Array.isArray(sources)) return
  // 按匹配度降序排序
  sortedDialogSources.value = [...sources].sort((a, b) => (b.score || 0) - (a.score || 0))
  sourceDialogVisible.value = true
}

async function sendMessage(text) {
  const q = (typeof text === 'string' ? text : inputText.value).trim()
  if (!q || sending.value) return
  if (!activeConvId.value) { await handleNewConversation(); if (!activeConvId.value) return }
  currentMessages.value.push({ question: q, answer: '', sources: [], loading: true })
  inputText.value = ''; await scrollToBottom(); sending.value = true

  try {
    // 流式 API：先逐字显示回答，再显示来源文档
    const result = await knowledgeApi.queryKnowledgeStream(
      { question: q, conversation_id: activeConvId.value },
      {
        onSources: (sources) => {
          const last = currentMessages.value[currentMessages.value.length - 1]
          if (last) last.sources = sources || []
          // 触发视图刷新
          currentMessages.value = [...currentMessages.value]
          scrollToBottom()
        },
        onText: (_incremental, fullText) => {
          const last = currentMessages.value[currentMessages.value.length - 1]
          if (last) last.answer = fullText
          // 每几轮滚动一次，避免过于频繁的 DOM 操作
          if (fullText.length % 40 < 10) scrollToBottom()
        },
        onDone: () => {
          const last = currentMessages.value[currentMessages.value.length - 1]
          if (last) last.loading = false
          scrollToBottom()
        },
        onError: (msg) => {
          const last = currentMessages.value[currentMessages.value.length - 1]
          if (last && !last.answer) last.answer = msg || '抱歉，服务暂时不可用，请稍后重试。'
          if (last) last.loading = false
        },
      },
    )

    // 确保最终来源和答案被设置（上面的回调已经处理了）
    const last = currentMessages.value[currentMessages.value.length - 1]
    if (last) {
      if (!last.answer) last.answer = result.answer || ''
      if (!last.sources || last.sources.length === 0) last.sources = result.sources || []
      last.loading = false
    }

    const conv = conversations.value.find(c => c.id === activeConvId.value)
    if (conv && conv.title === '新对话') conv.title = q.slice(0, 24) + (q.length > 24 ? '...' : '')
  } catch {
    const last = currentMessages.value[currentMessages.value.length - 1]
    last.answer = '抱歉，服务暂时不可用，请稍后重试。'; last.loading = false
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}

async function scrollToBottom() { await nextTick(); if (msgContainer.value) msgContainer.value.scrollTop = msgContainer.value.scrollHeight }

async function handleExport() {
  if (currentMessages.value.length === 0) { ElMessage.warning('暂无对话可导出'); return }
  exporting.value = true
  try {
    const queryContent = currentMessages.value.map(m => `${m.question}|${m.answer}`).join('; ')
    const blob = await knowledgeApi.exportData({ query: queryContent, format: 'pdf' })
    if (blob.type && blob.type.includes('application/json')) { const text = await blob.text(); try { const err = JSON.parse(text); ElMessage.error(err.detail || '导出失败'); return } catch { ElMessage.error('导出失败'); return } }
    const url = window.URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url
    const userId = authStore.user?.id || authStore.realName || '用户'; const now = new Date()
    a.download = `${userId}_${now.getFullYear()}${String(now.getMonth()+1).padStart(2,'0')}${String(now.getDate()).padStart(2,'0')}_${String(now.getHours()).padStart(2,'0')}${String(now.getMinutes()).padStart(2,'0')}${String(now.getSeconds()).padStart(2,'0')}.pdf`
    document.body.appendChild(a); a.click(); document.body.removeChild(a); window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) { ElMessage.error('导出失败') } finally { exporting.value = false }
}

async function handleApply(documentId) {
  applyForm.value.document_id = documentId
  applyForm.value.reason = '通过问答溯源发起访问申请'
  applyForm.value.reviewer_ids = []
  applyForm.value.expected_hours = 24
  await fetchReviewers()
  applyDialogVisible.value = true
}

async function handleViewDocument(documentId) {
  try {
    const url = documentsApi.getViewDocumentUrl(documentId)
    window.open(url, '_blank')
  } catch { ElMessage.warning('查看失败，请检查权限') }
}

async function handleDownloadDocument(documentId) {
  try {
    const res = await documentsApi.downloadDocument(documentId)
      if (res instanceof Blob) { const url = window.URL.createObjectURL(res); const a = document.createElement('a'); a.href = url; a.download = `document_${documentId}`; document.body.appendChild(a); a.click(); document.body.removeChild(a); window.URL.revokeObjectURL(url); ElMessage.success('下载成功') }
    else ElMessage.warning('下载失败，请检查权限')
  } catch { ElMessage.warning('下载失败，请检查权限') }
}

async function handleToggleFavorite(documentId) {
  // 在所有消息的 sources 中查找该文档的收藏状态
  let currentSrc = null
  for (const msg of currentMessages.value) {
    if (!msg.sources) continue
    const found = msg.sources.find(s => s.document_id === documentId)
    if (found) { currentSrc = found; break }
  }
  const wasFavorited = currentSrc ? !!currentSrc.is_favorited : false

  try {
    if (wasFavorited) {
      await documentsApi.removeFavorite(documentId)
      ElMessage.success('已取消收藏')
    } else {
      await documentsApi.addFavorite(documentId)
      ElMessage.success('已收藏')
    }
    // 更新本地所有消息中该文档的收藏状态
    currentMessages.value = currentMessages.value.map(msg => ({
      ...msg,
      sources: (msg.sources || []).map(s =>
        s.document_id === documentId ? { ...s, is_favorited: !wasFavorited } : s
      ),
    }))
  } catch {
    ElMessage.warning('操作失败，请稍后重试')
  }
}

async function submitApply() {
  if (!applyForm.value.reason.trim()) { ElMessage.warning('请填写申请原因'); return }
  if (!applyForm.value.reviewer_ids || applyForm.value.reviewer_ids.length === 0) {
    ElMessage.warning('请至少选择一名审核员/管理员')
    return
  }
  applying.value = true
  try {
    await documentsApi.applyAccess(applyForm.value.document_id, {
      reason: applyForm.value.reason,
      reviewer_ids: applyForm.value.reviewer_ids,
      expected_hours: applyForm.value.expected_hours,
    })
    ElMessage.success('申请已提交，等待部门管理员或审核员审核')
    applyDialogVisible.value = false
  } catch { /* handled */ } finally { applying.value = false }
}
</script>

<style scoped>
.qa-wrapper {
  display: flex;
  height: calc(100vh - 96px);
  gap: 0;
  position: relative;
  background: var(--color-bg-page);
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}

.qa-history {
  width: 260px;
  background: var(--color-bg-card);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 16px;
  border-bottom: 1px solid var(--color-border-light);
}

.history-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.history-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  cursor: pointer;
  margin-bottom: 4px;
  transition: all 0.2s ease;
  border: 1px solid transparent;
}

.history-item:hover {
  background: var(--color-bg-hover);
  border-color: var(--color-border);
}

.history-item.active {
  background: var(--color-primary-light);
  border-color: #7dd3fc;
  box-shadow: 0 2px 6px rgba(14, 165, 233, 0.08);
}

.history-item.active .history-title {
  color: var(--color-primary-active);
  font-weight: 600;
}

.history-left {
  flex: 1;
  min-width: 0;
}

.history-title {
  display: block;
  font-size: 13px;
  color: var(--color-text-regular);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
  line-height: 1.4;
}

.history-time {
  font-size: 11px;
  color: var(--color-text-placeholder);
  margin-top: 4px;
}

.history-delete {
  flex-shrink: 0;
  margin-left: 4px;
  color: var(--color-text-disabled);
  opacity: 0;
  transition: all 0.2s ease;
}

.history-item:hover .history-delete {
  opacity: 1;
  color: var(--color-danger);
}

.history-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--color-text-placeholder);
  font-size: 13px;
  padding: 20px;
  text-align: center;
}

.history-footer {
  display: none;
}

.qa-chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-page);
  min-width: 0;
}

.chat-welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  overflow-y: auto;
}

.welcome-icon {
  margin-bottom: 28px;
}

.welcome-pulse {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100px;
  height: 100px;
  background: var(--color-primary-gradient);
  border-radius: 28px;
  box-shadow: 0 8px 24px rgba(14, 165, 233, 0.25);
  animation: pulse 3s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 8px 24px rgba(14, 165, 233, 0.25); transform: scale(1); }
  50% { box-shadow: 0 12px 36px rgba(14, 165, 233, 0.35); transform: scale(1.03); }
}

.welcome-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-text-primary);
  margin: 0 0 12px;
  letter-spacing: -0.5px;
}

.welcome-desc {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0 0 36px;
}

.quick-prompts {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  max-width: 680px;
  justify-content: center;
}

.prompt-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  cursor: pointer;
  font-size: 13px;
  color: var(--color-text-regular);
  transition: all 0.2s ease;
  font-weight: 500;
}

.prompt-card:hover {
  background: var(--color-primary-light);
  border-color: #7dd3fc;
  color: var(--color-primary-active);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(14, 165, 233, 0.1);
}

.prompt-card-mini {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  cursor: pointer;
  font-size: 12px;
  color: var(--color-text-secondary);
  transition: all 0.2s ease;
}

.prompt-card-mini:hover {
  background: var(--color-primary-light);
  border-color: #7dd3fc;
  color: var(--color-primary-hover);
}

.quick-prompts-inline {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0 20px 12px;
  justify-content: flex-start;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 28px 36px;
}

.msg-group {
  margin-bottom: 32px;
  max-width: 900px;
  margin-left: auto;
  margin-right: auto;
}

.msg-row {
  display: flex;
  margin-bottom: 14px;
}

.msg-user {
  justify-content: flex-end;
  gap: 12px;
}

.msg-ai {
  align-items: flex-start;
  gap: 12px;
}

.msg-avatar {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  flex-shrink: 0;
}

.user-avatar {
  background: var(--color-primary-gradient);
  box-shadow: 0 2px 8px rgba(14, 165, 233, 0.25);
}

.ai-avatar {
  background: linear-gradient(135deg, #e0f2fe, #f0f9ff);
  border: 1px solid #bae6fd;
  box-shadow: 0 2px 6px rgba(14, 165, 233, 0.08);
}

.avatar-text {
  font-size: 12px;
  font-weight: 700;
  color: var(--color-primary);
}

.msg-bubble {
  max-width: 78%;
  padding: 14px 18px;
  border-radius: var(--radius-lg);
  font-size: 14px;
  line-height: 1.75;
  position: relative;
}

.user-bubble {
  background: var(--color-primary-gradient);
  color: #ffffff;
  border-bottom-right-radius: 4px;
  box-shadow: 0 4px 12px rgba(14, 165, 233, 0.2);
  font-weight: 500;
}

.ai-bubble {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-bottom-left-radius: 4px;
  box-shadow: var(--shadow-sm);
  color: var(--color-text-regular);
}

.thinking-dots {
  display: flex;
  align-items: center;
  padding: 8px 0;
  gap: 4px;
}

.thinking-dots span {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-primary);
  margin-right: 2px;
  animation: bounce 1.4s infinite;
}

.thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.4s; }

.thinking-text {
  background: transparent !important;
  width: auto !important;
  height: auto !important;
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-left: 8px;
  animation: none !important;
}

@keyframes bounce {
  0%, 80%, 100% { opacity: 0.4; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-6px); }
}

.answer-md {
  color: var(--color-text-regular);
}

.answer-md :deep(mark),
.answer-md :deep(strong) {
  background: #fef3c7;
  color: #92400e;
  font-weight: 600;
  padding: 1px 4px;
  border-radius: 3px;
}

.answer-md :deep(p) { margin: 0 0 10px; }

.answer-md :deep(p:last-child) { margin-bottom: 0; }

.answer-md :deep(code) {
  background: var(--color-border-light);
  color: var(--color-primary-active);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  font-family: 'SF Mono', Menlo, Monaco, Consolas, monospace;
}

.answer-md :deep(pre) {
  background: #0f172a;
  border-radius: var(--radius-md);
  padding: 16px;
  overflow-x: auto;
  margin: 12px 0;
  border: 1px solid #334155;
}

.answer-md :deep(pre code) {
  background: transparent;
  color: #e2e8f0;
  padding: 0;
  font-size: 13px;
  line-height: 1.6;
}

.answer-md :deep(ul),
.answer-md :deep(ol) {
  padding-left: 24px;
  margin: 10px 0;
}

.answer-md :deep(li) {
  margin-bottom: 6px;
  line-height: 1.7;
}

.answer-md :deep(h1),
.answer-md :deep(h2),
.answer-md :deep(h3) {
  margin: 18px 0 10px;
  color: var(--color-text-primary);
  font-weight: 600;
}

.answer-md :deep(h1) { font-size: 20px; border-bottom: 2px solid var(--color-border); padding-bottom: 8px; }
.answer-md :deep(h2) { font-size: 17px; }
.answer-md :deep(h3) { font-size: 15px; }

.answer-md :deep(blockquote) {
  border-left: 3px solid var(--color-primary);
  background: var(--color-primary-lighter);
  margin: 12px 0;
  padding: 12px 16px;
  border-radius: 0 8px 8px 0;
  color: var(--color-primary-active);
}

.answer-md :deep(a) {
  color: var(--color-primary);
  text-decoration: none;
  border-bottom: 1px solid #7dd3fc;
}

.answer-md :deep(a:hover) {
  color: var(--color-primary-active);
  border-bottom-color: var(--color-primary-active);
}

.source-refs {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--color-border-light);
}

.source-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-bottom: 0;
  font-weight: 600;
  letter-spacing: 0.3px;
}

.clickable {
  cursor: pointer;
  transition: color 0.2s;
}

.clickable:hover {
  color: var(--color-primary);
}

.clickable:hover .source-arrow {
  transform: translateX(3px);
}

.source-arrow {
  margin-left: 2px;
  transition: transform 0.2s;
}

.source-dialog-body {
  max-height: 70vh;
  overflow-y: auto;
  padding-right: 6px;
}

.source-dialog-body::-webkit-scrollbar {
  width: 5px;
}

.source-dialog-body::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 4px;
}

.source-label :deep(.el-icon) {
  color: var(--color-primary);
}

.chat-input-bar {
  padding: 18px 24px;
  border-top: 1px solid var(--color-border);
  background: var(--color-bg-card);
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  background: var(--color-bg-card);
  border: 2px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 10px 16px;
  transition: all 0.2s ease;
  max-width: 900px;
  margin: 0 auto;
}

.input-wrapper:focus-within {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 4px rgba(14, 165, 233, 0.1);
}

.chat-textarea {
  flex: 1;
}

.input-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.char-hint {
  font-size: 11px;
  color: #94a3b8;
}

.qa-quick-actions {
  position: fixed;
  bottom: 32px;
  right: 32px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  z-index: 10;
}

:deep(.el-textarea__inner) {
  background: transparent;
  border: none;
  box-shadow: none;
  color: var(--color-text-primary);
  resize: none;
  font-size: 14px;
  line-height: 1.7;
}

:deep(.el-textarea__inner::placeholder) {
  color: var(--color-text-placeholder);
}

/* Scrollbar */
.history-list::-webkit-scrollbar,
.chat-messages::-webkit-scrollbar {
  width: 6px;
}

.history-list::-webkit-scrollbar-track,
.chat-messages::-webkit-scrollbar-track {
  background: transparent;
}

.history-list::-webkit-scrollbar-thumb,
.chat-messages::-webkit-scrollbar-thumb {
  background: var(--color-text-disabled);
  border-radius: 3px;
}

.history-list::-webkit-scrollbar-thumb:hover,
.chat-messages::-webkit-scrollbar-thumb:hover {
  background: var(--color-text-placeholder);
}
</style>