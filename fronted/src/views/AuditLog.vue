<template>
  <div class="audit-log">
    <!-- Header -->
    <header class="header">
      <div class="container">
        <div class="header-content">
          <div class="page-title">
            <router-link to="/" class="back-link">
              ← 返回容器列表
            </router-link>
            <h1>操作审计日志</h1>
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

    <!-- Main Content -->
    <main class="main-content">
      <div class="container">
        <!-- 设置卡片 -->
        <div class="card settings-card">
          <div class="settings-row">
            <div class="settings-info">
              <h3 class="settings-title">日志保留设置</h3>
              <p class="settings-desc">
                审计日志将在数据库中保留 <strong>{{ retentionDays }}</strong> 天，过期日志将被自动清理。
                <span v-if="retentionDays !== defaultRetentionDays">（默认：{{ defaultRetentionDays }} 天）</span>
              </p>
            </div>
            <div class="settings-actions">
              <button class="btn btn-outline btn-sm" @click="openRetentionModal">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="3"></circle>
                  <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"></path>
                </svg>
                修改保留天数
              </button>
              <button class="btn btn-secondary btn-sm" @click="handleCleanup" :disabled="cleanupLoading">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
                {{ cleanupLoading ? '清理中...' : '手动清理过期日志' }}
              </button>
            </div>
          </div>
        </div>

        <!-- 筛选栏 -->
        <div class="filter-bar">
          <div class="filter-group">
            <label class="filter-label">操作类型</label>
            <select v-model="filters.action" class="filter-select" @change="applyFilters">
              <option value="">全部</option>
              <option value="login">登录</option>
              <option value="change_password">修改密码</option>
              <option value="create_user">创建用户</option>
              <option value="update_user">更新用户</option>
              <option value="delete_user">删除用户</option>
              <option value="create_permission">创建权限</option>
              <option value="delete_permission">删除权限</option>
              <option value="list_containers">查看容器列表</option>
              <option value="view_container_info">查看容器信息</option>
              <option value="view_container_logs">查看容器日志</option>
              <option value="export_logs">导出日志</option>
              <option value="start_container">启动容器</option>
              <option value="stop_container">停止容器</option>
              <option value="restart_container">重启容器</option>
              <option value="delete_container">删除容器</option>
              <option value="batch_start_containers">批量启动容器</option>
              <option value="batch_stop_containers">批量停止容器</option>
              <option value="batch_delete_containers">批量删除容器</option>
              <option value="view_stats">查看统计</option>
              <option value="view_image_layers">查看镜像层</option>
              <option value="update_settings">更新设置</option>
              <option value="view_audit_logs">查看审计日志</option>
              <option value="other">其他操作</option>
            </select>
          </div>
          
          <div class="filter-group">
            <label class="filter-label">状态</label>
            <select v-model="filters.status" class="filter-select" @change="applyFilters">
              <option value="">全部</option>
              <option value="success">成功</option>
              <option value="failed">失败</option>
            </select>
          </div>
          
          <div class="filter-group">
            <label class="filter-label">开始日期</label>
            <input type="date" v-model="filters.startDate" class="filter-input" @change="applyFilters" />
          </div>
          
          <div class="filter-group">
            <label class="filter-label">结束日期</label>
            <input type="date" v-model="filters.endDate" class="filter-input" @change="applyFilters" />
          </div>
          
          <div class="filter-actions">
            <button class="btn btn-outline btn-sm" @click="resetFilters">
              重置筛选
            </button>
            <button class="btn btn-primary btn-sm" @click="fetchAuditLogs">
              刷新
            </button>
          </div>
        </div>

        <!-- 加载状态 -->
        <div v-if="loading" class="loading-state">
          <div class="loading-spinner"></div>
          <p>加载中...</p>
        </div>

        <!-- 错误状态 -->
        <div v-else-if="error" class="error-state">
          <div class="error-icon">⚠️</div>
          <p>{{ error }}</p>
          <button class="btn btn-primary" @click="fetchAuditLogs">重试</button>
        </div>

        <!-- 日志列表 -->
        <div v-else class="card">
          <div v-if="auditLogs.length === 0" class="empty-state">
            <div class="empty-icon">📋</div>
            <p>暂无审计日志</p>
          </div>

          <div v-else>
            <div class="log-list">
              <table class="table">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>用户</th>
                    <th>操作</th>
                    <th>资源</th>
                    <th>描述</th>
                    <th>IP地址</th>
                    <th>状态</th>
                    <th class="text-right">详情</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="log in auditLogs" :key="log.id" class="log-row">
                    <td class="text-muted text-small">
                      {{ formatDate(log.created_at) }}
                    </td>
                    <td>
                      <div class="user-cell-small">
                        <span class="user-avatar-tiny">{{ log.username ? log.username.charAt(0).toUpperCase() : '?' }}</span>
                        <span class="text-ellipsis">{{ log.username || '未知' }}</span>
                      </div>
                    </td>
                    <td>
                      <span class="action-badge">
                        {{ getActionLabel(log.action) }}
                      </span>
                    </td>
                    <td class="text-muted text-small">
                      {{ log.resource_type || '-' }}
                      <span v-if="log.resource_id" class="text-ellipsis resource-id">{{ log.resource_id }}</span>
                    </td>
                    <td class="description-cell">
                      <span class="text-ellipsis">{{ log.description || '-' }}</span>
                    </td>
                    <td class="text-small text-muted">
                      {{ log.ip_address || '-' }}
                    </td>
                    <td>
                      <span class="badge" :class="log.status === 'success' ? 'badge-success' : 'badge-danger'">
                        {{ log.status === 'success' ? '成功' : '失败' }}
                      </span>
                    </td>
                    <td class="text-right">
                      <button 
                        class="btn btn-ghost btn-sm action-btn"
                        @click="openDetailModal(log)"
                        title="查看详情"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                          <circle cx="12" cy="12" r="3"></circle>
                        </svg>
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- 分页 -->
            <div v-if="totalPages > 1" class="pagination">
              <button 
                class="btn btn-outline btn-sm"
                :disabled="currentPage <= 1"
                @click="changePage(currentPage - 1)"
              >
                上一页
              </button>
              <span class="pagination-info">
                第 {{ currentPage }} 页，共 {{ totalPages }} 页（{{ total }} 条记录）
              </span>
              <button 
                class="btn btn-outline btn-sm"
                :disabled="currentPage >= totalPages"
                @click="changePage(currentPage + 1)"
              >
                下一页
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- 日志详情模态框 -->
    <div v-if="showDetailModal" class="modal-overlay" @click.self="closeDetailModal">
      <div class="modal modal-large">
        <div class="modal-header">
          <h3 class="modal-title">操作详情</h3>
          <button class="modal-close" @click="closeDetailModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="selectedLog" class="detail-content">
            <div class="detail-row">
              <span class="detail-label">操作时间</span>
              <span class="detail-value">{{ formatDate(selectedLog.created_at) }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">用户</span>
              <span class="detail-value">
                {{ selectedLog.username || '未知' }}
                <span v-if="selectedLog.user_id" class="text-muted">(ID: {{ selectedLog.user_id }})</span>
              </span>
            </div>
            <div class="detail-row">
              <span class="detail-label">操作类型</span>
              <span class="detail-value">
                <span class="action-badge">{{ getActionLabel(selectedLog.action) }}</span>
              </span>
            </div>
            <div class="detail-row">
              <span class="detail-label">操作状态</span>
              <span class="detail-value">
                <span class="badge" :class="selectedLog.status === 'success' ? 'badge-success' : 'badge-danger'">
                  {{ selectedLog.status === 'success' ? '成功' : '失败' }}
                </span>
              </span>
            </div>
            <div class="detail-row">
              <span class="detail-label">资源类型</span>
              <span class="detail-value">{{ selectedLog.resource_type || '-' }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">资源ID</span>
              <span class="detail-value font-mono">{{ selectedLog.resource_id || '-' }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">描述</span>
              <span class="detail-value">{{ selectedLog.description || '-' }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">IP地址</span>
              <span class="detail-value">{{ selectedLog.ip_address || '-' }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">用户代理</span>
              <span class="detail-value text-small text-muted">{{ selectedLog.user_agent || '-' }}</span>
            </div>
            <div v-if="selectedLog.error_message" class="detail-row">
              <span class="detail-label">错误信息</span>
              <span class="detail-value text-error">{{ selectedLog.error_message }}</span>
            </div>
            <div v-if="selectedLog.details" class="detail-row detail-row-full">
              <span class="detail-label">详细数据</span>
              <pre class="detail-value detail-json">{{ formatJson(selectedLog.details) }}</pre>
            </div>
          </div>
          
          <div class="modal-footer">
            <button class="btn btn-outline" @click="closeDetailModal">
              关闭
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 修改保留天数模态框 -->
    <div v-if="showRetentionModal" class="modal-overlay" @click.self="closeRetentionModal">
      <div class="modal modal-small">
        <div class="modal-header">
          <h3 class="modal-title">修改日志保留天数</h3>
          <button class="modal-close" @click="closeRetentionModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="retentionModalError" class="form-error">{{ retentionModalError }}</div>
          
          <form @submit.prevent="handleUpdateRetention">
            <div class="form-group">
              <label class="form-label">保留天数 <span class="required">*</span></label>
              <input 
                type="number" 
                v-model.number="retentionForm.days" 
                class="form-input"
                placeholder="请输入保留天数"
                :disabled="retentionModalLoading"
                min="1"
                max="3650"
                required
              />
              <p class="form-hint">
                允许范围：1-3650 天。超过保留期的日志将被自动清理。
              </p>
            </div>
            
            <div class="modal-footer">
              <button type="button" class="btn btn-outline" @click="closeRetentionModal" :disabled="retentionModalLoading">
                取消
              </button>
              <button type="submit" class="btn btn-primary" :disabled="retentionModalLoading || !retentionForm.days">
                {{ retentionModalLoading ? '保存中...' : '保存' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- Toast 提示 -->
    <div v-if="toastMessage" class="toast" :class="toastType">
      {{ toastMessage }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { useAuth } from '../composables/useAuth'


const router = useRouter()
const { isAdmin, currentUser, logout } = useAuth()


if (!isAdmin.value) {
  router.push('/')
}


const auditLogs = ref([])
const loading = ref(true)
const error = ref(null)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const cleanupLoading = ref(false)

const totalPages = computed(() => Math.ceil(total.value / pageSize.value))

const filters = ref({
  action: '',
  status: '',
  startDate: '',
  endDate: ''
})

const retentionDays = ref(90)
const defaultRetentionDays = ref(90)

const showDetailModal = ref(false)
const selectedLog = ref(null)

const showRetentionModal = ref(false)
const retentionModalLoading = ref(false)
const retentionModalError = ref('')
const retentionForm = ref({
  days: 90
})

const toastMessage = ref('')
const toastType = ref('success')
let toastTimeout = null


const actionLabels = {
  'login': '登录',
  'logout': '登出',
  'change_password': '修改密码',
  'create_user': '创建用户',
  'update_user': '更新用户',
  'delete_user': '删除用户',
  'create_permission': '创建权限',
  'update_permission': '更新权限',
  'delete_permission': '删除权限',
  'list_containers': '查看容器列表',
  'view_container_info': '查看容器信息',
  'view_container_logs': '查看容器日志',
  'export_logs': '导出日志',
  'start_container': '启动容器',
  'stop_container': '停止容器',
  'restart_container': '重启容器',
  'delete_container': '删除容器',
  'batch_start_containers': '批量启动容器',
  'batch_stop_containers': '批量停止容器',
  'batch_delete_containers': '批量删除容器',
  'view_stats': '查看统计',
  'view_image_layers': '查看镜像层',
  'update_settings': '更新设置',
  'view_audit_logs': '查看审计日志',
  'other': '其他操作'
}


const fetchRetentionDays = async () => {
  try {
    const response = await axios.get('/api/audit/retention')
    if (response.data.success) {
      retentionDays.value = response.data.data.retention_days
      defaultRetentionDays.value = response.data.data.default_retention_days
    }
  } catch (err) {
    console.error('获取保留天数失败:', err)
  }
}


const fetchAuditLogs = async () => {
  try {
    loading.value = true
    error.value = null
    
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    
    if (filters.value.action) {
      params.action = filters.value.action
    }
    if (filters.value.status) {
      params.status = filters.value.status
    }
    if (filters.value.startDate) {
      params.start_date = filters.value.startDate
    }
    if (filters.value.endDate) {
      params.end_date = filters.value.endDate
    }
    
    const response = await axios.get('/api/audit/logs', { params })
    
    if (response.data.success) {
      auditLogs.value = response.data.data
      total.value = response.data.total
    } else {
      error.value = response.data.error || '获取审计日志失败'
    }
  } catch (err) {
    error.value = err.response?.data?.message || err.message || '获取审计日志失败'
  } finally {
    loading.value = false
  }
}


const applyFilters = () => {
  currentPage.value = 1
  fetchAuditLogs()
}


const resetFilters = () => {
  filters.value = {
    action: '',
    status: '',
    startDate: '',
    endDate: ''
  }
  currentPage.value = 1
  fetchAuditLogs()
}


const changePage = (page) => {
  if (page >= 1 && page <= totalPages.value) {
    currentPage.value = page
    fetchAuditLogs()
  }
}


const getActionLabel = (action) => {
  return actionLabels[action] || action
}


const openDetailModal = (log) => {
  selectedLog.value = { ...log }
  showDetailModal.value = true
}


const closeDetailModal = () => {
  showDetailModal.value = false
  selectedLog.value = null
}


const openRetentionModal = () => {
  retentionForm.value.days = retentionDays.value
  retentionModalError.value = ''
  showRetentionModal.value = true
}


const closeRetentionModal = () => {
  showRetentionModal.value = false
  retentionForm.value = {
    days: retentionDays.value
  }
  retentionModalError.value = ''
}


const handleUpdateRetention = async () => {
  if (!retentionForm.value.days || retentionForm.value.days < 1 || retentionForm.value.days > 3650) {
    retentionModalError.value = '请输入有效的保留天数（1-3650）'
    return
  }
  
  try {
    retentionModalLoading.value = true
    retentionModalError.value = ''
    
    const response = await axios.put('/api/audit/retention', {
      retention_days: retentionForm.value.days
    })
    
    if (response.data.success) {
      retentionDays.value = retentionForm.value.days
      showToast('保留天数更新成功', 'success')
      closeRetentionModal()
    } else {
      retentionModalError.value = response.data.error || '更新失败'
    }
  } catch (err) {
    retentionModalError.value = err.response?.data?.message || err.message || '更新失败'
  } finally {
    retentionModalLoading.value = false
  }
}


const handleCleanup = async () => {
  try {
    cleanupLoading.value = true
    
    const response = await axios.post('/api/audit/cleanup')
    
    if (response.data.success) {
      showToast(response.data.message, 'success')
      fetchAuditLogs()
      fetchRetentionDays()
    }
  } catch (err) {
    showToast(err.response?.data?.message || err.message || '清理失败', 'error')
  } finally {
    cleanupLoading.value = false
  }
}


const formatDate = (timestamp) => {
  if (!timestamp) return 'N/A'
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}


const formatJson = (obj) => {
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
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
  fetchRetentionDays()
  fetchAuditLogs()
})
</script>

<style scoped>
.audit-log {
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
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 1rem;
}

.card {
  background-color: var(--bg-primary);
  border-radius: 0.75rem;
  padding: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.settings-card {
  margin-bottom: 1.5rem;
}

.settings-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1.5rem;
}

.settings-info {
  flex: 1;
}

.settings-title {
  font-size: 1.125rem;
  font-weight: 600;
  margin: 0 0 0.5rem 0;
}

.settings-desc {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.5;
}

.settings-actions {
  display: flex;
  gap: 0.5rem;
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 1.5rem;
  padding: 1rem;
  background-color: var(--bg-primary);
  border-radius: 0.75rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.filter-label {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.filter-select,
.filter-input {
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  outline: none;
  transition: border-color 0.2s;
}

.filter-select:focus,
.filter-input:focus {
  border-color: var(--primary-color);
}

.filter-actions {
  display: flex;
  gap: 0.5rem;
  align-items: flex-end;
  margin-left: auto;
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

.loading-state {
  color: var(--text-secondary);
}

.error-icon,
.empty-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
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

.table {
  width: 100%;
  border-collapse: collapse;
}

.table th {
  text-align: left;
  padding: 0.75rem 1rem;
  font-weight: 600;
  font-size: 0.75rem;
  color: var(--text-secondary);
  border-bottom: 1px solid var(--border-color);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.table td {
  padding: 0.875rem 1rem;
  border-bottom: 1px solid var(--border-color);
  font-size: 0.875rem;
  vertical-align: middle;
}

.table tr:last-child td {
  border-bottom: none;
}

.log-row:hover {
  background-color: var(--bg-secondary);
}

.text-right {
  text-align: right;
}

.text-muted {
  color: var(--text-secondary);
}

.text-small {
  font-size: 0.75rem;
}

.text-error {
  color: var(--error-color);
}

.text-ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 150px;
  display: inline-block;
}

.user-cell-small {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.user-avatar-tiny {
  width: 20px;
  height: 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.625rem;
  flex-shrink: 0;
}

.resource-id {
  font-family: 'Courier New', monospace;
  margin-left: 0.25rem;
  max-width: 100px;
}

.description-cell {
  max-width: 200px;
}

.badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
}

.badge-success {
  background-color: #d1fae5;
  color: #065f46;
}

.badge-danger {
  background-color: #fee2e2;
  color: #991b1b;
}

.action-badge {
  display: inline-block;
  padding: 0.25rem 0.625rem;
  border-radius: 0.375rem;
  font-size: 0.75rem;
  font-weight: 500;
  background-color: #eff6ff;
  color: #1d4ed8;
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

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 1rem;
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border-color);
}

.pagination-info {
  font-size: 0.875rem;
  color: var(--text-secondary);
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

.btn-secondary {
  background-color: #4b5563;
  color: white;
}

.btn-secondary:hover:not(:disabled) {
  background-color: #374151;
}

.btn-danger {
  background-color: var(--error-color);
  color: white;
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
}

.action-btn {
  min-width: 28px;
  padding: 0.25rem;
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
  width: 450px;
}

.modal-large {
  width: 700px;
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
  padding-top: 1.5rem;
}

.detail-content {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.detail-row {
  display: flex;
  gap: 1rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--border-color);
}

.detail-row:last-child {
  border-bottom: none;
}

.detail-row-full {
  flex-direction: column;
}

.detail-label {
  min-width: 100px;
  font-weight: 500;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.detail-value {
  flex: 1;
  word-break: break-all;
}

.detail-json {
  background-color: var(--bg-secondary);
  padding: 1rem;
  border-radius: 0.375rem;
  font-size: 0.75rem;
  overflow-x: auto;
  max-height: 300px;
  overflow-y: auto;
  margin: 0;
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

.font-mono {
  font-family: 'Courier New', monospace;
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

@media (max-width: 768px) {
  .header-content {
    flex-direction: column;
    gap: 1rem;
    align-items: flex-start;
  }
  
  .filter-bar {
    flex-direction: column;
  }
  
  .filter-actions {
    margin-left: 0;
    width: 100%;
  }
  
  .table {
    font-size: 0.75rem;
  }
  
  .table th,
  .table td {
    padding: 0.5rem;
  }
  
  .modal {
    max-width: 100%;
    max-height: 95vh;
  }
  
  .modal-large {
    width: 100%;
  }
  
  .modal-small {
    width: 100%;
  }
}
</style>