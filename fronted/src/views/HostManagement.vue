<template>
  <div class="host-management">
    <header class="header">
      <div class="container">
        <div class="header-content">
          <div class="page-title">
            <router-link to="/" class="back-link">
              ← 返回容器列表
            </router-link>
            <h1>主机管理</h1>
          </div>
          <div class="header-actions">
            <div class="user-menu">
              <span class="user-info">
                <span class="user-avatar">{{ currentUser?.username?.charAt(0).toUpperCase() }}</span>
                <span class="user-name">{{ currentUser?.username }}</span>
                <span class="user-role role-admin">管理员</span>
              </span>
              <button class="btn btn-ghost btn-sm" @click="logout" title="退出登录">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                  <polyline points="16 17 21 12 16 7"></polyline>
                  <line x1="21" y1="12" x2="9" y2="12"></line>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </header>

    <main class="main-content">
      <div class="container">
        <div class="action-bar">
          <button class="btn btn-primary" @click="openCreateModal">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            新增主机
          </button>
          <button class="btn btn-outline" @click="fetchHosts">
            刷新
          </button>
        </div>

        <div v-if="loading" class="loading-state">
          <div class="loading-spinner"></div>
          <p>加载中...</p>
        </div>

        <div v-else-if="error" class="error-state">
          <div class="error-icon">⚠️</div>
          <p>{{ error }}</p>
          <button class="btn btn-primary" @click="fetchHosts">重试</button>
        </div>

        <div v-else class="card">
          <div v-if="hosts.length === 0" class="empty-state">
            <div class="empty-icon">🖥️</div>
            <p>暂无 Docker 主机配置</p>
            <p class="text-muted">当前只使用本地 Docker 连接</p>
            <button class="btn btn-primary" @click="openCreateModal">添加远程 Docker 主机</button>
          </div>

          <div v-else class="host-list">
            <div class="local-host-card" v-if="localHostStatus">
              <div class="host-card-header">
                <div class="host-info">
                  <div class="host-icon local">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"></path>
                    </svg>
                  </div>
                  <div class="host-details">
                    <h3 class="host-name">本地主机</h3>
                    <p class="host-url">unix:///var/run/docker.sock</p>
                    <p class="host-status">
                      <span 
                        class="connection-status"
                        :class="localHostStatus.connected ? 'connected' : 'disconnected'"
                      >
                        <span class="status-dot"></span>
                        {{ localHostStatus.connected ? '已连接' : '连接失败' }}
                      </span>
                    </p>
                  </div>
                </div>
                <div class="host-stats">
                  <div class="stat-item">
                    <span class="stat-value">{{ localHostStatus.container_count }}</span>
                    <span class="stat-label">容器</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-value running">{{ localHostStatus.running_count }}</span>
                    <span class="stat-label">运行中</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-value stopped">{{ localHostStatus.stopped_count }}</span>
                    <span class="stat-label">已停止</span>
                  </div>
                  <div class="stat-item" v-if="localHostStatus.cpu_usage !== null">
                    <span class="stat-value cpu">{{ localHostStatus.cpu_usage }}%</span>
                    <span class="stat-label">CPU</span>
                  </div>
                  <div class="stat-item" v-if="localHostStatus.memory_usage !== null && localHostStatus.memory_total">
                    <span class="stat-value memory">{{ formatBytes(localHostStatus.memory_usage) }}</span>
                    <span class="stat-label">内存</span>
                  </div>
                </div>
              </div>
              <div class="host-card-footer">
                <button class="btn btn-outline btn-sm" @click="testLocalConnection" :disabled="testingLocal">
                  {{ testingLocal ? '测试中...' : '测试连接' }}
                </button>
              </div>
            </div>

            <div 
              v-for="host in hosts" 
              :key="host.id" 
              class="host-card"
              :class="{ 'host-card-inactive': !host.is_active }"
            >
              <div class="host-card-header">
                <div class="host-info">
                  <div class="host-icon" :class="host.is_active ? 'active' : 'inactive'">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                      <line x1="8" y1="21" x2="16" y2="21"></line>
                      <line x1="12" y1="17" x2="12" y2="21"></line>
                    </svg>
                  </div>
                  <div class="host-details">
                    <h3 class="host-name">
                      {{ host.name }}
                      <span v-if="!host.is_active" class="badge badge-secondary">已禁用</span>
                    </h3>
                    <p class="host-url">{{ host.host }}</p>
                    <p class="host-description" v-if="host.description">{{ host.description }}</p>
                    <p class="host-status" v-if="hostStatuses[host.id]">
                      <span 
                        class="connection-status"
                        :class="hostStatuses[host.id].connected ? 'connected' : 'disconnected'"
                      >
                        <span class="status-dot"></span>
                        {{ hostStatuses[host.id].connected ? '已连接' : '连接失败' }}
                      </span>
                      <span v-if="!hostStatuses[host.id].connected && hostStatuses[host.id].error_message" class="error-text">
                        ({{ hostStatuses[host.id].error_message }})
                      </span>
                    </p>
                    <p class="host-meta">
                      创建时间: {{ formatDate(host.created_at) }}
                      <span v-if="host.updated_at && host.updated_at !== host.created_at">
                        | 更新时间: {{ formatDate(host.updated_at) }}
                      </span>
                    </p>
                  </div>
                </div>
                <div class="host-stats" v-if="hostStatuses[host.id]">
                  <div class="stat-item">
                    <span class="stat-value">{{ hostStatuses[host.id].container_count }}</span>
                    <span class="stat-label">容器</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-value running">{{ hostStatuses[host.id].running_count }}</span>
                    <span class="stat-label">运行中</span>
                  </div>
                  <div class="stat-item">
                    <span class="stat-value stopped">{{ hostStatuses[host.id].stopped_count }}</span>
                    <span class="stat-label">已停止</span>
                  </div>
                  <div class="stat-item" v-if="hostStatuses[host.id].cpu_usage !== null">
                    <span class="stat-value cpu">{{ hostStatuses[host.id].cpu_usage }}%</span>
                    <span class="stat-label">CPU</span>
                  </div>
                  <div class="stat-item" v-if="hostStatuses[host.id].memory_usage !== null">
                    <span class="stat-value memory">{{ formatBytes(hostStatuses[host.id].memory_usage) }}</span>
                    <span class="stat-label">内存</span>
                  </div>
                </div>
              </div>
              <div class="host-card-footer">
                <div class="action-buttons">
                  <button 
                    class="btn btn-ghost btn-sm action-btn"
                    @click="testHostConnection(host)"
                    :disabled="testingHost === host.id"
                    title="测试连接"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                      <polyline points="22 4 12 14.01 9 11.01"></polyline>
                    </svg>
                    {{ testingHost === host.id ? '测试中...' : '测试连接' }}
                  </button>
                  <button 
                    class="btn btn-ghost btn-sm action-btn"
                    @click="openEditModal(host)"
                    title="编辑主机"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                    </svg>
                    编辑
                  </button>
                  <button 
                    class="btn btn-ghost btn-sm action-btn action-btn-danger"
                    @click="confirmDeleteHost(host)"
                    title="删除主机"
                    :disabled="deleteInProgress === host.id"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="3 6 5 6 21 6"></polyline>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                      <line x1="10" y1="11" x2="10" y2="17"></line>
                      <line x1="14" y1="11" x2="14" y2="17"></line>
                    </svg>
                    删除
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <div v-if="showHostModal" class="modal-overlay" @click.self="closeHostModal">
      <div class="modal modal-medium">
        <div class="modal-header">
          <h3 class="modal-title">{{ editingHost ? '编辑主机' : '添加主机' }}</h3>
          <button class="modal-close" @click="closeHostModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="hostModalError" class="form-error">{{ hostModalError }}</div>
          
          <form @submit.prevent="handleSubmitHost">
            <div class="form-group">
              <label class="form-label">主机名称 <span class="required">*</span></label>
              <input 
                type="text" 
                v-model="hostForm.name" 
                class="form-input"
                placeholder="例如: Production Server, Staging Node"
                :disabled="hostModalLoading"
                required
              />
            </div>
            
            <div class="form-group">
              <label class="form-label">Docker 地址 <span class="required">*</span></label>
              <input 
                type="text" 
                v-model="hostForm.host" 
                class="form-input"
                placeholder="例如: tcp://192.168.1.100:2375 或 unix:///var/run/docker.sock"
                :disabled="hostModalLoading"
                required
              />
              <p class="form-hint">
                <strong>支持的格式:</strong><br>
                • <code>tcp://192.168.1.100:2375</code> - 远程 Docker 守护进程<br>
                • <code>unix:///var/run/docker.sock</code> - 本地 Unix socket (默认)
              </p>
            </div>
            
            <div class="form-group">
              <label class="form-label">描述</label>
              <textarea 
                v-model="hostForm.description" 
                class="form-input"
                placeholder="主机描述（可选）"
                :disabled="hostModalLoading"
                rows="3"
              ></textarea>
            </div>
            
            <div class="form-group">
              <label class="checkbox-label">
                <input 
                  type="checkbox" 
                  v-model="hostForm.is_active"
                  :disabled="hostModalLoading"
                />
                <span>启用此主机</span>
              </label>
            </div>
            
            <div class="modal-footer">
              <button type="button" class="btn btn-outline" @click="closeHostModal" :disabled="hostModalLoading">
                取消
              </button>
              <button type="button" class="btn btn-outline" @click="testCurrentHostConnection" :disabled="hostModalLoading || !hostForm.host">
                测试连接
              </button>
              <button type="submit" class="btn btn-primary" :disabled="hostModalLoading || !hostForm.name || !hostForm.host">
                {{ hostModalLoading ? '提交中...' : (editingHost ? '保存' : '创建') }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <div v-if="showDeleteConfirm" class="modal-overlay" @click.self="closeDeleteConfirm">
      <div class="modal modal-small">
        <div class="modal-header">
          <h3 class="modal-title">确认删除</h3>
        </div>
        <div class="modal-body">
          <p>确定要删除主机 "<strong>{{ deletingHost?.name }}</strong>" 吗？</p>
          <p class="delete-info">此操作不可撤销。</p>
          
          <div class="modal-footer">
            <button type="button" class="btn btn-outline" @click="closeDeleteConfirm" :disabled="deleteConfirmLoading">
              取消
            </button>
            <button type="button" class="btn btn-danger" @click="executeDeleteHost" :disabled="deleteConfirmLoading">
              {{ deleteConfirmLoading ? '删除中...' : '确认删除' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="toastMessage" class="toast" :class="toastType">
      {{ toastMessage }}
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useAuth } from '../composables/useAuth'


const router = useRouter()
const { isAdmin, currentUser, logout, currentToken } = useAuth()


if (!isAdmin.value) {
  router.push('/')
}


const hosts = ref([])
const loading = ref(true)
const error = ref(null)

const localHostStatus = ref(null)
const hostStatuses = ref({})

const testingLocal = ref(false)
const testingHost = ref(null)

const showHostModal = ref(false)
const editingHost = ref(null)
const hostModalLoading = ref(false)
const hostModalError = ref('')
const hostForm = ref({
  name: '',
  host: 'tcp://',
  description: '',
  is_active: true
})

const showDeleteConfirm = ref(false)
const deletingHost = ref(null)
const deleteInProgress = ref(null)
const deleteConfirmLoading = ref(false)

const toastMessage = ref('')
const toastType = ref('success')
let toastTimeout = null

let statusPollingInterval = null


const fetchHosts = async () => {
  try {
    loading.value = true
    error.value = null
    
    const response = await axios.get('/api/hosts')
    
    if (response.data.success) {
      hosts.value = response.data.data
    } else {
      error.value = response.data.error || '获取主机列表失败'
    }
  } catch (err) {
    error.value = err.response?.data?.message || err.message || '获取主机列表失败'
  } finally {
    loading.value = false
  }
}


const fetchHostStatuses = async () => {
  try {
    const response = await axios.get('/api/hosts/status')
    
    if (response.data.success) {
      const statuses = response.data.data
      
      for (const status of statuses) {
        if (status.host_id === 0) {
          localHostStatus.value = status
        } else {
          hostStatuses.value[status.host_id] = status
        }
      }
    }
  } catch (err) {
    console.error('获取主机状态失败:', err)
  }
}


const testLocalConnection = async () => {
  testingLocal.value = true
  try {
    const response = await axios.post('/api/hosts/0/test')
    if (response.data.success) {
      showToast('本地 Docker 连接成功', 'success')
    } else {
      showToast(response.data.message || '连接失败', 'error')
    }
    fetchHostStatuses()
  } catch (err) {
    showToast(err.response?.data?.message || err.message || '连接测试失败', 'error')
  } finally {
    testingLocal.value = false
  }
}


const testHostConnection = async (host) => {
  testingHost.value = host.id
  try {
    const response = await axios.post(`/api/hosts/${host.id}/test`)
    if (response.data.success) {
      showToast(`主机 ${host.name} 连接成功`, 'success')
    } else {
      showToast(response.data.message || '连接失败', 'error')
    }
    fetchHostStatuses()
  } catch (err) {
    showToast(err.response?.data?.message || err.message || '连接测试失败', 'error')
  } finally {
    testingHost.value = null
  }
}


const testCurrentHostConnection = async () => {
  if (!hostForm.value.host) {
    showToast('请输入 Docker 地址', 'error')
    return
  }
  
  if (hostForm.value.host.startsWith('unix://')) {
    await testLocalConnection()
  } else {
    showToast('请先保存主机配置后再测试连接', 'info')
  }
}


const openCreateModal = () => {
  editingHost.value = null
  hostForm.value = {
    name: '',
    host: 'tcp://',
    description: '',
    is_active: true
  }
  hostModalError.value = ''
  showHostModal.value = true
}


const openEditModal = (host) => {
  editingHost.value = { ...host }
  hostForm.value = {
    name: host.name,
    host: host.host,
    description: host.description || '',
    is_active: host.is_active
  }
  hostModalError.value = ''
  showHostModal.value = true
}


const closeHostModal = () => {
  showHostModal.value = false
  editingHost.value = null
  hostForm.value = {
    name: '',
    host: 'tcp://',
    description: '',
    is_active: true
  }
  hostModalError.value = ''
}


const handleSubmitHost = async () => {
  if (!hostForm.value.name) {
    hostModalError.value = '请输入主机名称'
    return
  }
  
  if (!hostForm.value.host) {
    hostModalError.value = '请输入 Docker 地址'
    return
  }
  
  try {
    hostModalLoading.value = true
    hostModalError.value = ''
    
    if (editingHost.value) {
      const updateData = {
        name: hostForm.value.name,
        host: hostForm.value.host,
        description: hostForm.value.description,
        is_active: hostForm.value.is_active
      }
      
      const response = await axios.put(`/api/hosts/${editingHost.value.id}`, updateData)
      
      if (response.data.success) {
        showToast('主机更新成功', 'success')
        closeHostModal()
        fetchHosts()
        fetchHostStatuses()
      } else {
        hostModalError.value = response.data.error || '更新主机失败'
      }
    } else {
      const response = await axios.post('/api/hosts', {
        name: hostForm.value.name,
        host: hostForm.value.host,
        description: hostForm.value.description,
        is_active: hostForm.value.is_active
      })
      
      if (response.data.success) {
        showToast('主机创建成功', 'success')
        closeHostModal()
        fetchHosts()
        fetchHostStatuses()
      } else {
        hostModalError.value = response.data.error || '创建主机失败'
      }
    }
  } catch (err) {
    hostModalError.value = err.response?.data?.message || err.message || '操作失败'
  } finally {
    hostModalLoading.value = false
  }
}


const confirmDeleteHost = (host) => {
  deletingHost.value = host
  showDeleteConfirm.value = true
}


const closeDeleteConfirm = () => {
  showDeleteConfirm.value = false
  deletingHost.value = null
}


const executeDeleteHost = async () => {
  if (!deletingHost.value) return
  
  try {
    deleteConfirmLoading.value = true
    deleteInProgress.value = deletingHost.value.id
    
    await axios.delete(`/api/hosts/${deletingHost.value.id}`)
    
    showToast('主机删除成功', 'success')
    closeDeleteConfirm()
    fetchHosts()
    fetchHostStatuses()
  } catch (err) {
    showToast(err.response?.data?.message || err.message || '删除失败', 'error')
  } finally {
    deleteConfirmLoading.value = false
    deleteInProgress.value = null
  }
}


const formatDate = (timestamp) => {
  if (!timestamp) return 'N/A'
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN')
}


const formatBytes = (bytes) => {
  if (bytes === 0 || !bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}


const showToast = (message, type = 'success') => {
  if (toastTimeout) {
    clearTimeout(toastTimeout)
  }
  toastMessage.value = message
  toastType.value = type
  toastTimeout = setTimeout(() => {
    toastMessage.value = ''
  }, 3000)
}


onMounted(() => {
  fetchHosts()
  fetchHostStatuses()
  
  statusPollingInterval = setInterval(() => {
    fetchHostStatuses()
  }, 10000)
})


onUnmounted(() => {
  if (statusPollingInterval) {
    clearInterval(statusPollingInterval)
  }
})
</script>

<style scoped>
.host-management {
  min-height: 100vh;
  background-color: var(--bg-secondary);
}

.header {
  background-color: var(--bg-primary);
  border-bottom: 1px solid var(--border-color);
  padding: 1rem 0;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.page-title h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
}

.back-link {
  color: var(--primary-color);
  text-decoration: none;
  font-size: 0.875rem;
}

.back-link:hover {
  text-decoration: underline;
}

.header-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.main-content {
  padding: 1.5rem 0;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 1rem;
}

.card {
  background-color: var(--bg-primary);
  border-radius: 0.75rem;
  padding: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.action-bar {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}

.loading-state,
.error-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  text-align: center;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 1rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.text-muted {
  color: var(--text-secondary);
}

.host-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.host-card,
.local-host-card {
  background-color: var(--bg-secondary);
  border-radius: 0.75rem;
  border: 1px solid var(--border-color);
  overflow: hidden;
  transition: box-shadow 0.2s, border-color 0.2s;
}

.host-card:hover,
.local-host-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border-color: var(--primary-color);
}

.host-card-inactive {
  opacity: 0.6;
}

.host-card-inactive:hover {
  border-color: var(--border-color);
}

.host-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 1.25rem;
  gap: 1.5rem;
}

.host-info {
  display: flex;
  gap: 1rem;
  flex: 1;
}

.host-icon {
  width: 56px;
  height: 56px;
  border-radius: 0.75rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.host-icon.local {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
}

.host-icon.active {
  background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
  color: white;
}

.host-icon.inactive {
  background: var(--bg-primary);
  color: var(--text-secondary);
  border: 2px dashed var(--border-color);
}

.host-details {
  flex: 1;
}

.host-name {
  font-size: 1.125rem;
  font-weight: 600;
  margin: 0 0 0.25rem 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.host-url {
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin: 0 0 0.25rem 0;
  word-break: break-all;
}

.host-description {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin: 0 0 0.5rem 0;
}

.host-status {
  margin: 0.5rem 0;
}

.connection-status {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
}

.connection-status.connected {
  color: var(--success-color);
}

.connection-status.disconnected {
  color: var(--error-color);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.connection-status.connected .status-dot {
  background-color: var(--success-color);
}

.connection-status.disconnected .status-dot {
  background-color: var(--error-color);
}

.error-text {
  color: var(--error-color);
  font-size: 0.75rem;
  margin-left: 0.5rem;
}

.host-meta {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin: 0.25rem 0 0 0;
}

.host-stats {
  display: flex;
  gap: 1.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 60px;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-value.running {
  color: var(--success-color);
}

.stat-value.stopped {
  color: var(--text-secondary);
}

.stat-value.cpu {
  color: #f59e0b;
}

.stat-value.memory {
  color: #8b5cf6;
}

.stat-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-top: 0.125rem;
}

.host-card-footer {
  padding: 0.75rem 1.25rem;
  background-color: var(--bg-primary);
  border-top: 1px solid var(--border-color);
}

.action-buttons {
  display: flex;
  gap: 0.5rem;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 1rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  border: none;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  text-decoration: none;
  transition: all 0.2s;
  gap: 0.5rem;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-outline {
  border: 1px solid var(--border-color);
}

.btn-outline:hover:not(:disabled) {
  background-color: var(--bg-secondary);
}

.btn-ghost {
  background-color: transparent;
}

.btn-ghost:hover:not(:disabled) {
  background-color: var(--bg-secondary);
}

.btn-primary {
  background-color: var(--primary-color);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background-color: #2563eb;
}

.btn-danger {
  background-color: var(--error-color);
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background-color: #dc2626;
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
}

.action-btn {
  min-width: auto;
  padding: 0.375rem 0.75rem;
}

.action-btn-danger {
  color: var(--error-color);
}

.action-btn-danger:hover:not(:disabled) {
  background-color: rgba(239, 68, 68, 0.1);
}

.user-menu {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.25rem 0.5rem;
  background-color: var(--bg-secondary);
  border-radius: 8px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.user-avatar {
  width: 28px;
  height: 28px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.875rem;
}

.user-name {
  font-weight: 500;
  font-size: 0.875rem;
}

.user-role {
  font-size: 0.7rem;
  padding: 0.125rem 0.375rem;
  border-radius: 4px;
}

.user-role.role-admin {
  background-color: rgba(245, 158, 11, 0.1);
  color: #d97706;
}

.badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
}

.badge-secondary {
  background-color: var(--bg-secondary);
  color: var(--text-secondary);
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 1rem;
}

.modal {
  background-color: var(--bg-primary);
  border-radius: 0.5rem;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
  max-width: 90vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
}

.modal-small {
  width: 400px;
}

.modal-medium {
  width: 550px;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.modal-title {
  font-size: 1.125rem;
  font-weight: 600;
  margin: 0;
}

.modal-close {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.25rem;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-close:hover {
  color: var(--text-primary);
}

.modal-body {
  padding: 1.5rem;
  overflow-y: auto;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding-top: 1rem;
}

.form-group {
  margin-bottom: 1.25rem;
  position: relative;
}

.form-label {
  display: block;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
}

.required {
  color: var(--error-color);
}

.form-input {
  width: 100%;
  padding: 0.75rem 1rem;
  font-size: 1rem;
  border: 2px solid #e5e7eb;
  border-radius: 8px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  box-sizing: border-box;
  font-family: inherit;
  resize: vertical;
  min-height: 44px;
}

.form-input:focus {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.form-input:disabled {
  background-color: var(--bg-secondary);
  cursor: not-allowed;
}

.form-hint {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-top: 0.25rem;
  line-height: 1.5;
}

.form-error {
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  color: #dc2626;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  font-size: 0.875rem;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  cursor: pointer;
}

.delete-info {
  color: var(--text-secondary);
  font-size: 0.875rem;
  margin-top: 0.5rem;
}

.toast {
  position: fixed;
  bottom: 1.5rem;
  left: 50%;
  transform: translateX(-50%);
  padding: 0.75rem 1.5rem;
  border-radius: 0.375rem;
  font-size: 0.875rem;
  font-weight: 500;
  z-index: 3000;
  animation: slideUp 0.3s ease;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}

.toast.success {
  background-color: var(--success-color);
  color: white;
}

.toast.error {
  background-color: var(--error-color);
  color: white;
}

.toast.info {
  background-color: var(--primary-color);
  color: white;
}

@media (max-width: 768px) {
  .header-content {
    flex-direction: column;
    gap: 1rem;
    align-items: flex-start;
  }
  
  .header-actions {
    width: 100%;
    flex-wrap: wrap;
  }
  
  .host-card-header {
    flex-direction: column;
    gap: 1rem;
  }
  
  .host-stats {
    width: 100%;
    justify-content: space-between;
  }
  
  .modal {
    max-width: 100%;
    max-height: 95vh;
  }
  
  .modal-medium {
    width: 100%;
  }
  
  .modal-small {
    width: 100%;
  }
}
</style>
