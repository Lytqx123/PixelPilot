<template>
  <div class="login-container">
    <div class="login-bg">
      <div class="shapes">
        <div class="shape shape-1"></div>
        <div class="shape shape-2"></div>
        <div class="shape shape-3"></div>
        <div class="shape shape-4"></div>
      </div>
      <div class="grid-pattern"></div>
    </div>

    <!-- 左侧品牌介绍(大屏显示) -->
    <div class="brand-panel">
      <div class="brand-content">
        <div class="brand-logo">
          <div class="logo-circle">
            <el-icon :size="40" color="#ffffff"><Cpu /></el-icon>
          </div>
        </div>
        <h1 class="brand-title">PixelPulse 像素脉动</h1>
        <p class="brand-subtitle">企业级多模态知识库引擎</p>
        <div class="brand-features">
          <div class="feature-item">
            <el-icon :size="18"><ChatDotRound /></el-icon>
            <span>智能问答 · 知识溯源</span>
          </div>
          <div class="feature-item">
            <el-icon :size="18"><Document /></el-icon>
            <span>多模态文档 · 权限管控</span>
          </div>
          <div class="feature-item">
            <el-icon :size="18"><Checked /></el-icon>
            <span>审核工作流 · 企业级安全</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧登录卡片 -->
    <div class="login-card">
      <div class="login-header">
        <div class="login-logo">
          <div class="logo-circle">
            <el-icon :size="34" color="#ffffff"><Cpu /></el-icon>
          </div>
        </div>
        <h2 class="login-title">欢迎登录</h2>
        <p class="login-subtitle">请输入您的账号密码</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        class="login-form"
        autocomplete="off"
        @keyup.enter="handleLogin"
      >
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="用户名"
            :prefix-icon="User"
            size="large"
            autocomplete="off"
            name="username"
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            :prefix-icon="Lock"
            size="large"
            show-password
            autocomplete="new-password"
            name="password"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            :loading="loading"
            class="login-btn"
            size="large"
            @click="handleLogin"
          >
            {{ loading ? '验证中...' : '登 录' }}
          </el-button>
        </el-form-item>
      </el-form>

      <div class="login-footer">
        <span>&copy; 2026 PixelPulse</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock, Cpu, ChatDotRound, Document, Checked } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()
const formRef = ref(null)
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
}

async function handleLogin() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    // 清除浏览器所有旧状态
    localStorage.clear()
    const res = await authStore.login(form.username, form.password)
    if (res && res.access_token) {
      ElMessage.success('登录成功')
      // 短暂延迟后跳转，确保后端服务就绪后再加载页面组件
      await new Promise(resolve => setTimeout(resolve, 300))
      await router.push('/knowledge')
    }
  } catch {
    // 错误信息已由 request.js 拦截器统一处理，此处无需重复提示
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  position: relative;
  display: flex;
  min-height: 100vh;
  background: linear-gradient(135deg, #0c4a6e 0%, #075985 30%, #0369a1 60%, #0284c7 100%);
  overflow: hidden;
}

.login-bg {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.shapes {
  position: absolute;
  inset: 0;
}

.shape {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
}

.shape-1 {
  width: 600px;
  height: 600px;
  background: #38bdf8;
  opacity: 0.4;
  top: -200px;
  right: -150px;
}

.shape-2 {
  width: 450px;
  height: 450px;
  background: #22d3ee;
  opacity: 0.3;
  bottom: -150px;
  left: -100px;
}

.shape-3 {
  width: 350px;
  height: 350px;
  background: #7dd3fc;
  opacity: 0.35;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

.shape-4 {
  width: 250px;
  height: 250px;
  background: #67e8f9;
  opacity: 0.25;
  top: 10%;
  left: 10%;
}

.grid-pattern {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
  background-size: 60px 60px;
}

/* 左侧品牌面板 */
.brand-panel {
  position: relative;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  z-index: 1;
}

.brand-content {
  max-width: 480px;
  color: #ffffff;
  animation: fadeInLeft 0.8s ease-out;
}

@keyframes fadeInLeft {
  from { opacity: 0; transform: translateX(-30px); }
  to { opacity: 1; transform: translateX(0); }
}

.brand-logo {
  margin-bottom: 28px;
}

.logo-circle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  height: 72px;
  background: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.25);
  border-radius: 20px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
}

.brand-title {
  font-size: 32px;
  font-weight: 700;
  color: #ffffff;
  margin: 0 0 12px 0;
  letter-spacing: 0.5px;
  line-height: 1.2;
}

.brand-subtitle {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.8);
  margin: 0 0 48px 0;
  letter-spacing: 1px;
}

.brand-features {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 15px;
  color: rgba(255, 255, 255, 0.9);
  font-weight: 500;
}

.feature-item :deep(.el-icon) {
  color: #7dd3fc;
  background: rgba(255, 255, 255, 0.1);
  padding: 8px;
  border-radius: 10px;
  box-sizing: content-box;
}

/* 右侧登录卡片 */
.login-card {
  position: relative;
  width: 440px;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.8);
  border-radius: 24px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12), 0 2px 8px rgba(0, 0, 0, 0.04);
  padding: 48px 44px 36px;
  margin: 40px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  animation: fadeInUp 0.6s ease-out;
  z-index: 1;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.login-header {
  text-align: center;
  margin-bottom: 36px;
}

.login-logo {
  margin-bottom: 16px;
}

.login-header .logo-circle {
  width: 60px;
  height: 60px;
  background: var(--color-primary-gradient);
  border: none;
  border-radius: 18px;
  box-shadow: 0 6px 16px rgba(14, 165, 233, 0.3);
}

.login-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-text-primary);
  margin: 0 0 8px 0;
  letter-spacing: 0.5px;
}

.login-subtitle {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 0;
  letter-spacing: 0.5px;
}

.login-form {
  margin-bottom: 24px;
}

.login-btn {
  width: 100%;
  height: 48px;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 6px;
  border-radius: 12px;
  background: var(--color-primary-gradient);
  border: none;
  box-shadow: 0 4px 14px rgba(14, 165, 233, 0.3);
  transition: all 0.3s;
}

.login-btn:hover {
  box-shadow: 0 8px 24px rgba(14, 165, 233, 0.4);
  transform: translateY(-1px);
}

.login-footer {
  text-align: center;
  padding-top: 20px;
  border-top: 1px solid var(--color-border-light);
}

.login-footer span {
  font-size: 12px;
  color: var(--color-text-placeholder);
}

:deep(.el-input__wrapper) {
  border-radius: 10px;
  background: var(--color-bg-hover);
  border: 1px solid var(--color-border);
  box-shadow: none;
  transition: all 0.3s;
}

:deep(.el-input__wrapper:hover) {
  border-color: #7dd3fc;
  background: #ffffff;
}

:deep(.el-input__wrapper.is-focus) {
  border-color: var(--color-primary);
  background: #ffffff;
  box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.1);
}

:deep(.el-input__inner) {
  color: var(--color-text-primary);
}

:deep(.el-input__inner::placeholder) {
  color: var(--color-text-placeholder);
}

/* 小屏隐藏品牌面板 */
@media (max-width: 900px) {
  .brand-panel {
    display: none;
  }
  .login-card {
    margin: 20px auto;
  }
}
</style>