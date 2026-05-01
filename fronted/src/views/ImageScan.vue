<template>
  <div class="image-scan">
    <header class="header">
      <div class="container">
        <div class="header-content">
          <div class="page-title">
            <router-link to="/" class="back-link">
              ← 返回容器列表
            </router-link>
            <h1>镜像安全扫描</h1>
          </div>
          <div class="header-actions">
            <div class="service-status" :class="trivyAvailable ? 'available' : 'unavailable'">
              <span class="status-dot"></span>
              <span class="status-text">Trivy: {{ trivyAvailable ? '可用' : '模拟模式' }}</span>
              <span v-if="trivyVersion" class="status-version">({{ trivyVersion }})</span>
            </div>
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
        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-icon total">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
              </svg>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ summary.total_vulnerabilities || 0 }}</div>
              <div class="stat-label">总漏洞数</div>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon critical">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="15" y1="9" x2="9" y2="15"></line>
                <line x1="9" y1="9" x2="15" y2="15"></line>
              </svg>
            </div>
            <div class="stat-info">
              <div class="stat-value critical">{{ summary.by_severity?.critical || 0 }}</div>
              <div class="stat-label">严重</div>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon high">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                <line x1="12" y1="9" x2="12" y2="13"></line>
                <line x1="12" y1="17" x2="12.01" y2="17"></line>
              </svg>
            </div>
            <div class="stat-info">
              <div class="stat-value high">{{ summary.by_severity?.high || 0 }}</div>
              <div class="stat-label">高危</div>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon medium">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="12 2 15.09 8.26 22 9 17 14.74 18.18 21.02 12 17.77 5.82 21.02 7 14.74 2 9 8.91 8.26 12 2"></polygon>
              </svg>
            </div>
            <div class="stat-info">
              <div class="stat-value medium">{{ summary.by_severity?.medium || 0 }}</div>
              <div class="stat-label">中危</div>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon scan">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="7" height="7"></rect>
                <rect x="14" y="3" width="7" height="7"></rect>
                <rect x="14" y="14" width="7" height="7"></rect>
                <rect x="3" y="14" width="7" height="7"></rect>
              </svg>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ summary.total_scans || 0 }}</div>
              <div class="stat-label">扫描次数</div>
            </div>
          </div>
        </div>

        <div class="action-bar">
          <button class="btn btn-primary" @click="openScanModal">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>
            </svg>
            新建扫描
          </button>
          <button class="btn btn-outline" @click="fetchScans">
            刷新
          </button>
          <div class="search-box">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <input 
              type="text" 
              v-model="searchQuery" 
              placeholder="搜索镜像名称..."
              @keyup.enter="fetchScans"
            />
          </div>
          <select v-model="filterStatus" class="form-input" @change="fetchScans">
            <option value="">全部状态</option>
            <option value="pending">待执行</option>
            <option value="running">扫描中</option>
            <option value="completed">已完成</option>
            <option value="failed">失败</option>
          </select>
        </div>

        <div v-if="loading" class="loading-state">
          <div class="loading-spinner"></div>
          <p>加载中...</p>
        </div>

        <div v-else-if="error" class="error-state">
          <div class="error-icon">⚠️</div>
          <p>{{ error }}</p>
          <button class="btn btn-primary" @click="fetchScans">重试</button>
        </div>

        <div v-else class="scan-list-container">
          <div v-if="scans.length === 0" class="empty-state">
            <div class="empty-icon">🔍</div>
            <p>暂无扫描记录</p>
            <p class="text-muted">点击上方"新建扫描"按钮开始扫描镜像</p>
          </div>

          <div v-else class="scan-list">
            <div 
              v-for="scan in scans" 
              :key="scan.id" 
              class="scan-card"
              @click="viewScanDetail(scan)"
            >
              <div class="scan-card-header">
                <div class="scan-icon" :class="getSeverityClass(scan)">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                  </svg>
                </div>
                <div class="scan-info">
                  <div class="scan-name">{{ scan.image_name }}</div>
                  <div class="scan-meta">
                    <span class="meta-item">
                      <span class="status-badge" :class="scan.status">
                        {{ getStatusText(scan.status) }}
                      </span>
                    </span>
                    <span class="meta-item" v-if="scan.status === 'running'">
                      进度: {{ scan.progress }}% - {{ scan.progress_message }}
                    </span>
                    <span class="meta-item" v-else-if="scan.status === 'completed'">
                      <span class="severity-count critical" v-if="scan.critical_count > 0">
                        严重: {{ scan.critical_count }}
                      </span>
                      <span class="severity-count high" v-if="scan.high_count > 0">
                        高危: {{ scan.high_count }}
                      </span>
                      <span class="severity-count medium" v-if="scan.medium_count > 0">
                        中危: {{ scan.medium_count }}
                      </span>
                      <span class="severity-count low" v-if="scan.total_vulnerabilities === 0">
                        无漏洞
                      </span>
                    </span>
                    <span class="meta-item" v-if="scan.created_at">
                      {{ formatDateTime(scan.created_at) }}
                    </span>
                  </div>
                </div>
              </div>
              <div class="scan-card-footer" v-if="scan.status === 'completed'">
                <div class="severity-bar">
                  <div 
                    v-if="scan.critical_count > 0" 
                    class="severity-segment critical" 
                    :style="{ width: (scan.critical_count / scan.total_vulnerabilities) * 100 + '%' }"
                  ></div>
                  <div 
                    v-if="scan.high_count > 0" 
                    class="severity-segment high" 
                    :style="{ width: (scan.high_count / scan.total_vulnerabilities) * 100 + '%' }"
                  ></div>
                  <div 
                    v-if="scan.medium_count > 0" 
                    class="severity-segment medium" 
                    :style="{ width: (scan.medium_count / scan.total_vulnerabilities) * 100 + '%' }"
                  ></div>
                  <div 
                    v-if="scan.low_count > 0" 
                    class="severity-segment low" 
                    :style="{ width: (scan.low_count / scan.total_vulnerabilities) * 100 + '%' }"
                  ></div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="totalPages > 1" class="pagination">
            <button 
              class="btn btn-outline btn-sm" 
              @click="currentPage = currentPage - 1; fetchScans()"
              :disabled="currentPage <= 1"
            >
              上一页
            </button>
            <span class="page-info">
              第 {{ currentPage }} 页 / 共 {{ totalPages }} 页 ({{ total }} 条记录)
            </span>
            <button 
              class="btn btn-outline btn-sm" 
              @click="currentPage = currentPage + 1; fetchScans()"
              :disabled="currentPage >= totalPages"
            >
              下一页
            </button>
          </div>
        </div>
      </div>
    </main>

    <div v-if="showScanModal" class="modal-overlay" @click.self="closeScanModal">
      <div class="modal modal-medium">
        <div class="modal-header">
          <h3 class="modal-title">新建镜像扫描</h3>
          <button class="modal-close" @click="closeScanModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="scanModalError" class="form-error">{{ scanModalError }}</div>
          
          <form @submit.prevent="handleScanImage">
            <div class="form-group">
              <label class="form-label">镜像名称 <span class="required">*</span></label>
              <input 
                type="text" 
                v-model="scanForm.image" 
                class="form-input"
                placeholder="例如: nginx, ubuntu, registry.example.com/my-image:latest"
                :disabled="scanModalLoading"
                required
              />
              <p class="form-hint">输入要扫描的镜像名称或 ID</p>
            </div>
            
            <div class="form-group">
              <label class="form-label">扫描类型</label>
              <select 
                v-model="scanForm.scan_type" 
                class="form-input"
                :disabled="scanModalLoading"
              >
                <option value="all">综合扫描（全部类型）</option>
                <option value="vulnerability">漏洞扫描</option>
                <option value="secret">敏感信息检测</option>
                <option value="config">配置风险检测</option>
              </select>
              <p class="form-hint">选择要执行的扫描类型</p>
            </div>
            
            <div class="form-group">
              <label class="form-label">使用仓库配置（可选）</label>
              <select 
                v-model="scanForm.registry_id" 
                class="form-input"
                :disabled="scanModalLoading || registries.length === 0"
              >
                <option :value="null">不使用私有仓库</option>
                <option v-for="reg in registries" :key="reg.id" :value="reg.id">
                  {{ reg.name }} ({{ reg.registry_type }})
                </option>
              </select>
              <p class="form-hint" v-if="registries.length === 0">
                暂无已配置的私有仓库，<router-link to="/registries" class="link">点击配置</router-link>
              </p>
            </div>
            
            <div class="modal-footer">
              <button type="button" class="btn btn-outline" @click="closeScanModal" :disabled="scanModalLoading">
                取消
              </button>
              <button type="submit" class="btn btn-primary" :disabled="scanModalLoading || !scanForm.image">
                {{ scanModalLoading ? '提交中...' : '开始扫描' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <div v-if="showDetailModal" class="modal-overlay modal-large" @click.self="closeDetailModal">
      <div class="modal modal-xlarge">
        <div class="modal-header">
          <h3 class="modal-title">扫描详情 - {{ selectedScan?.image_name }}</h3>
          <button class="modal-close" @click="closeDetailModal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <div v-if="detailLoading" class="loading-state">
            <div class="loading-spinner"></div>
            <p>加载中...</p>
          </div>
          <div v-else-if="scanDetail">
            <div class="detail-section">
              <h4>基本信息</h4>
              <div class="detail-grid">
                <div class="detail-item">
                  <span class="detail-label">状态</span>
                  <span class="status-badge" :class="scanDetail.status">
                    {{ getStatusText(scanDetail.status) }}
                  </span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">扫描类型</span>
                  <span class="detail-value">{{ scanDetail.scan_type }}</span>
                </div>
                <div class="detail-item">
                  <span class="detail-label">创建时间</span>
                  <span class="detail-value">{{ formatDateTime(scanDetail.created_at) }}</span>
                </div>
                <div v-if="scanDetail.completed_at" class="detail-item">
                  <span class="detail-label">完成时间</span>
                  <span class="detail-value">{{ formatDateTime(scanDetail.completed_at) }}</span>
                </div>
              </div>
            </div>

            <div v-if="scanDetail.status === 'completed'" class="detail-section">
              <h4>漏洞统计</h4>
              <div class="severity-summary">
                <div class="severity-summary-item critical">
                  <span class="count">{{ scanDetail.critical_count }}</span>
                  <span class="label">严重</span>
                </div>
                <div class="severity-summary-item high">
                  <span class="count">{{ scanDetail.high_count }}</span>
                  <span class="label">高危</span>
                </div>
                <div class="severity-summary-item medium">
                  <span class="count">{{ scanDetail.medium_count }}</span>
                  <span class="label">中危</span>
                </div>
                <div class="severity-summary-item low">
                  <span class="count">{{ scanDetail.low_count }}</span>
                  <span class="label">低危</span>
                </div>
                <div class="severity-summary-item secret" v-if="scanDetail.secret_count > 0">
                  <span class="count">{{ scanDetail.secret_count }}</span>
                  <span class="label">敏感信息</span>
                </div>
                <div class="severity-summary-item config" v-if="scanDetail.config_issue_count > 0">
                  <span class="count">{{ scanDetail.config_issue_count }}</span>
                  <span class="label">配置问题</span>
                </div>
              </div>
            </div>

            <div v-if="scanDetail.vulnerabilities && scanDetail.vulnerabilities.length > 0" class="detail-section">
              <h4>漏洞列表 ({{ scanDetail.vulnerabilities.length }})</h4>
              <div class="vulnerability-list">
                <div 
                  v-for="vuln in scanDetail.vulnerabilities" 
                  :key="vuln.id" 
                  class="vulnerability-item"
                >
                  <div class="vulnerability-header">
                    <span class="severity-badge" :class="vuln.severity">
                      {{ getSeverityText(vuln.severity) }}
                    </span>
                    <span class="vulnerability-id">
                      {{ vuln.cve_id || vuln.vulnerability_id }}
                    </span>
                    <span class="vulnerability-package">
                      {{ vuln.package_name }} {{ vuln.installed_version }}
                    </span>
                  </div>
                  <div class="vulnerability-title">{{ vuln.title }}</div>
                  <div v-if="vuln.description" class="vulnerability-description">
                    {{ vuln.description }}
                  </div>
                  <div class="vulnerability-meta">
                    <span v-if="vuln.fixed_version" class="fix-version">
                      修复版本: {{ vuln.fixed_version }}
                    </span>
                    <span v-if="vuln.cvss_score" class="cvss-score">
                      CVSS 分数: {{ vuln.cvss_score }}
                    </span>
                    <a v-if="vuln.primary_url" :href="vuln.primary_url" target="_blank" class="reference-link">
                      查看详情 →
                    </a>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="scanDetail.secrets && scanDetail.secrets.length > 0" class="detail-section">
              <h4>敏感信息检测 ({{ scanDetail.secrets.length }})</h4>
              <div class="secret-list">
                <div 
                  v-for="secret in scanDetail.secrets" 
                  :key="secret.id" 
                  class="secret-item"
                >
                  <div class="secret-header">
                    <span class="severity-badge" :class="secret.severity">
                      {{ getSeverityText(secret.severity) }}
                    </span>
                    <span class="secret-type">{{ secret.secret_type }}</span>
                    <span class="secret-filename">{{ secret.filename }}</span>
                  </div>
                  <div v-if="secret.description" class="secret-description">
                    {{ secret.description }}
                  </div>
                </div>
              </div>
            </div>

            <div v-if="scanDetail.config_issues && scanDetail.config_issues.length > 0" class="detail-section">
              <h4>配置问题 ({{ scanDetail.config_issues.length }})</h4>
              <div class="config-issue-list">
                <div 
                  v-for="issue in scanDetail.config_issues" 
                  :key="issue.id" 
                  class="config-issue-item"
                >
                  <div class="config-issue-header">
                    <span class="severity-badge" :class="issue.severity">
                      {{ getSeverityText(issue.severity) }}
                    </span>
                    <span class="config-issue-type">{{ issue.check_type }}</span>
                    <span class="config-issue-category">{{ issue.category }}</span>
                  </div>
                  <div class="config-issue-message">{{ issue.message }}</div>
                  <div v-if="issue.remediation" class="config-issue-remediation">
                    <strong>修复建议:</strong> {{ issue.remediation }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showDeleteConfirm" class="modal-overlay" @click.self="closeDeleteConfirm">
      <div class="modal modal-small">
        <div class="modal-header">
          <h3 class="modal-title">确认删除</h3>
        </div>
        <div class="modal-body">
          <p>确定要删除扫描记录 "<strong>{{ deletingScan?.image_name }}</strong>" 吗？</p>
          
          <div class="modal-footer">
            <button type="button" class="btn btn-outline" @click="closeDeleteConfirm" :disabled="deleteConfirmLoading">
              取消
            </button>
            <button type="button" class="btn btn-danger" @click="executeDeleteScan" :disabled="deleteConfirmLoading">
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
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import { scanApi, registryApi, imageApi } from '../api/containerApi'


const router = useRouter()
const { isAdmin, currentUser, logout } = useAuth()


if (!isAdmin.value) {
  router.push('/')
}


const trivyAvailable = ref(false)
const trivyVersion = ref(null)
const summary = ref({
  total_vulnerabilities: 0,
  total_scans: 0,
  by_severity: {
    critical: 0,
    high: 0,
    medium: 0,
    low: 0,
    unknown: 0
  },
  recent_scans: [],
  top_images_by_severity: []
})

const scans = ref([])
const registries = ref([])
const loading = ref(true)
const error = ref(null)
const searchQuery = ref('')
const filterStatus = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const totalPages = ref(0)

const selectedScan = ref(null)
const scanDetail = ref(null)
const detailLoading = ref(false)

const showScanModal = ref(false)
const scanModalLoading = ref(false)
const scanModalError = ref('')
const scanForm = ref({
  image: '',
  scan_type: 'all',
  registry_id: null
})

const showDetailModal = ref(false)
const showDeleteConfirm = ref(false)
const deletingScan = ref(null)
const deleteConfirmLoading = ref(false)

const toastMessage = ref('')
const toastType = ref('success')
let toastTimeout = null


const fetchTrivyStatus = async () => {
  try {
    const result = await scanApi.getTrivyStatus()
    if (result.success) {
      trivyAvailable.value = result.data?.available ?? false
      trivyVersion.value = result.data?.version
    }
  } catch (err) {
    console.error('获取 Trivy 状态失败:', err)
  }
}


const fetchSummary = async () => {
  try {
    const result = await scanApi.getScansSummary({ days: 30 })
    if (result.success) {
      summary.value = result.data || summary.value
    }
  } catch (err) {
    console.error('获取扫描摘要失败:', err)
  }
}


const fetchScans = async () => {
  try {
    loading.value = true
    error.value = null
    
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    
    if (searchQuery.value) {
      params.search = searchQuery.value
    }
    if (filterStatus.value) {
      params.status = filterStatus.value
    }
    
    const result = await scanApi.getScans(params)
    
    if (result.success) {
      scans.value = result.data?.scans || []
      total.value = result.data?.total || 0
      totalPages.value = result.data?.total_pages || 1
    } else {
      error.value = result.message || '获取扫描列表失败'
    }
  } catch (err) {
    error.value = err.message || '获取扫描列表失败'
  } finally {
    loading.value = false
  }
}


const fetchRegistries = async () => {
  try {
    const result = await registryApi.getRegistries()
    if (result.success) {
      registries.value = result.data || []
    }
  } catch (err) {
    console.error('获取仓库列表失败:', err)
  }
}


const getStatusText = (status) => {
  const map = {
    pending: '待执行',
    running: '扫描中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消'
  }
  return map[status] || status
}


const getSeverityText = (severity) => {
  const map = {
    critical: '严重',
    high: '高危',
    medium: '中危',
    low: '低危',
    unknown: '未知'
  }
  return map[severity] || severity
}


const getSeverityClass = (scan) => {
  if (scan.status !== 'completed') return 'default'
  if (scan.critical_count > 0) return 'critical'
  if (scan.high_count > 0) return 'high'
  if (scan.medium_count > 0) return 'medium'
  return 'clean'
}


const formatDateTime = (dateStr) => {
  if (!dateStr) return 'N/A'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}


const openScanModal = () => {
  scanForm.value = {
    image: '',
    scan_type: 'all',
    registry_id: null
  }
  scanModalError.value = ''
  showScanModal.value = true
}


const closeScanModal = () => {
  showScanModal.value = false
  scanForm.value = {
    image: '',
    scan_type: 'all',
    registry_id: null
  }
  scanModalError.value = ''
}


const handleScanImage = async () => {
  if (!scanForm.value.image) {
    scanModalError.value = '请输入镜像名称'
    return
  }
  
  try {
    scanModalLoading.value = true
    scanModalError.value = ''
    
    const data = {
      image: scanForm.value.image,
      scan_type: scanForm.value.scan_type
    }
    
    if (scanForm.value.registry_id) {
      data.registry_id = scanForm.value.registry_id
    }
    
    const result = await scanApi.scanImage(data)
    
    if (result.success) {
      showToast('扫描任务已提交', 'success')
      closeScanModal()
      fetchScans()
      fetchSummary()
    } else {
      scanModalError.value = result.message || '提交扫描任务失败'
    }
  } catch (err) {
    scanModalError.value = err.message || '提交扫描任务失败'
  } finally {
    scanModalLoading.value = false
  }
}


const viewScanDetail = async (scan) => {
  selectedScan.value = scan
  detailLoading.value = true
  showDetailModal.value = true
  
  try {
    const result = await scanApi.getScanDetail(scan.id)
    
    if (result.success) {
      scanDetail.value = result.data
    }
  } catch (err) {
    console.error('获取扫描详情失败:', err)
  } finally {
    detailLoading.value = false
  }
}


const closeDetailModal = () => {
  showDetailModal.value = false
  scanDetail.value = null
  selectedScan.value = null
}


const confirmDeleteScan = (scan) => {
  deletingScan.value = scan
  showDeleteConfirm.value = true
}


const closeDeleteConfirm = () => {
  showDeleteConfirm.value = false
  deletingScan.value = null
}


const executeDeleteScan = async () => {
  if (!deletingScan.value) return
  
  try {
    deleteConfirmLoading.value = true
    
    const result = await scanApi.deleteScan(deletingScan.value.id)
    
    if (result.success) {
      showToast('扫描记录删除成功', 'success')
      closeDeleteConfirm()
      fetchScans()
      fetchSummary()
    } else {
      showToast(result.message || '删除失败', 'error')
    }
  } catch (err) {
    showToast(err.message || '删除失败', 'error')
  } finally {
    deleteConfirmLoading.value = false
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
  fetchTrivyStatus()
  fetchSummary()
  fetchScans()
  fetchRegistries()
})


let refreshInterval
const startAutoRefresh = () => {
  refreshInterval = setInterval(() => {
    const hasRunningScans = scans.value.some(s => s.status === 'pending' || s.status === 'running')
    if (hasRunningScans) {
      fetchScans()
      fetchSummary()
    }
  }, 5000)
}

const stopAutoRefresh = () => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
}

watch(scans, (newScans) => {
  const hasRunning = newScans.some(s => s.status === 'pending' || s.status === 'running')
  if (hasRunning && !refreshInterval) {
    startAutoRefresh()
  } else if (!hasRunning && refreshInterval) {
    stopAutoRefresh()
  }
}, { deep: true })
</script>

<style scoped>
.image-scan {
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

.service-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0.75rem;
  border-radius: 8px;
  font-size: 0.75rem;
}

.service-status.available {
  background-color: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.service-status.unavailable {
  background-color: rgba(245, 158, 11, 0.1);
  color: #d97706;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: currentColor;
}

.status-version {
  opacity: 0.7;
}

.main-content {
  padding: 1.5rem 0;
}

.container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 1rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background-color: var(--bg-primary);
  border-radius: 0.75rem;
  border: 1px solid var(--border-color);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon.total {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: white;
}

.stat-icon.critical {
  background-color: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.stat-icon.high {
  background-color: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
}

.stat-icon.medium {
  background-color: rgba(234, 179, 8, 0.1);
  color: #eab308;
}

.stat-icon.scan {
  background-color: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-value.critical {
  color: #ef4444;
}

.stat-value.high {
  color: #f59e0b;
}

.stat-value.medium {
  color: #eab308;
}

.stat-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-top: 0.25rem;
}

.action-bar {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background-color: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  padding: 0.5rem 0.75rem;
  flex: 1;
  min-width: 200px;
}

.search-box input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 0.875rem;
}

.search-box input::placeholder {
  color: var(--text-secondary);
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

.link {
  color: var(--primary-color);
  text-decoration: underline;
  cursor: pointer;
}

.link:hover {
  text-decoration: none;
}

.scan-list-container {
  background-color: var(--bg-primary);
  border-radius: 0.75rem;
  padding: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.scan-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.scan-card {
  background-color: var(--bg-secondary);
  border-radius: 0.75rem;
  border: 1px solid var(--border-color);
  padding: 1.25rem;
  cursor: pointer;
  transition: all 0.2s;
}

.scan-card:hover {
  border-color: var(--primary-color);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.scan-card-header {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.scan-icon {
  width: 40px;
  height: 40px;
  border-radius: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.scan-icon.default {
  background-color: rgba(156, 163, 175, 0.1);
  color: #9ca3af;
}

.scan-icon.critical {
  background-color: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.scan-icon.high {
  background-color: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
}

.scan-icon.medium {
  background-color: rgba(234, 179, 8, 0.1);
  color: #eab308;
}

.scan-icon.clean {
  background-color: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}

.scan-info {
  flex: 1;
  min-width: 0;
}

.scan-name {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
  word-break: break-all;
}

.scan-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.status-badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
}

.status-badge.pending {
  background-color: rgba(156, 163, 175, 0.1);
  color: #9ca3af;
}

.status-badge.running {
  background-color: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

.status-badge.completed {
  background-color: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}

.status-badge.failed {
  background-color: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.status-badge.critical {
  background-color: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.status-badge.high {
  background-color: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
}

.status-badge.medium {
  background-color: rgba(234, 179, 8, 0.1);
  color: #eab308;
}

.status-badge.low {
  background-color: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}

.severity-count {
  font-weight: 600;
}

.severity-count.critical {
  color: #ef4444;
}

.severity-count.high {
  color: #f59e0b;
}

.severity-count.medium {
  color: #eab308;
}

.severity-count.low {
  color: #22c55e;
}

.scan-card-footer {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-color);
}

.severity-bar {
  display: flex;
  height: 8px;
  border-radius: 4px;
  overflow: hidden;
}

.severity-segment {
  height: 100%;
  min-width: 0;
}

.severity-segment.critical {
  background-color: #ef4444;
}

.severity-segment.high {
  background-color: #f59e0b;
}

.severity-segment.medium {
  background-color: #eab308;
}

.severity-segment.low {
  background-color: #22c55e;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-color);
}

.page-info {
  font-size: 0.875rem;
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

.modal-large {
  width: 800px;
  max-height: 85vh;
}

.modal-xlarge {
  width: 1000px;
  max-height: 85vh;
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

.detail-section {
  margin-bottom: 1.5rem;
}

.detail-section h4 {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 1rem 0;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-color);
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.detail-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.detail-value {
  font-size: 0.875rem;
  color: var(--text-primary);
  font-family: 'Courier New', monospace;
  word-break: break-all;
}

.severity-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
}

.severity-summary-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  padding: 0.75rem 1.25rem;
  border-radius: 0.5rem;
  min-width: 80px;
}

.severity-summary-item.critical {
  background-color: rgba(239, 68, 68, 0.1);
}

.severity-summary-item.high {
  background-color: rgba(245, 158, 11, 0.1);
}

.severity-summary-item.medium {
  background-color: rgba(234, 179, 8, 0.1);
}

.severity-summary-item.low {
  background-color: rgba(34, 197, 94, 0.1);
}

.severity-summary-item.secret {
  background-color: rgba(168, 85, 247, 0.1);
}

.severity-summary-item.config {
  background-color: rgba(6, 182, 212, 0.1);
}

.severity-summary-item .count {
  font-size: 1.5rem;
  font-weight: 700;
}

.severity-summary-item.critical .count {
  color: #ef4444;
}

.severity-summary-item.high .count {
  color: #f59e0b;
}

.severity-summary-item.medium .count {
  color: #eab308;
}

.severity-summary-item.low .count {
  color: #22c55e;
}

.severity-summary-item.secret .count {
  color: #a855f7;
}

.severity-summary-item.config .count {
  color: #06b6d4;
}

.severity-summary-item .label {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.vulnerability-list,
.secret-list,
.config-issue-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.vulnerability-item,
.secret-item,
.config-issue-item {
  padding: 1rem;
  background-color: var(--bg-secondary);
  border-radius: 0.5rem;
  border: 1px solid var(--border-color);
}

.vulnerability-header,
.secret-header,
.config-issue-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
  flex-wrap: wrap;
}

.vulnerability-id,
.secret-type,
.config-issue-type {
  font-family: 'Courier New', monospace;
  font-size: 0.75rem;
  color: var(--primary-color);
  font-weight: 600;
}

.vulnerability-package,
.secret-filename,
.config-issue-category {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-left: auto;
}

.vulnerability-title,
.config-issue-message {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
}

.vulnerability-description,
.secret-description,
.config-issue-remediation {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-bottom: 0.5rem;
  line-height: 1.5;
}

.vulnerability-meta {
  display: flex;
  align-items: center;
  gap: 1rem;
  font-size: 0.75rem;
  flex-wrap: wrap;
}

.fix-version {
  color: #22c55e;
  font-weight: 600;
}

.cvss-score {
  color: var(--text-secondary);
}

.reference-link {
  color: var(--primary-color);
  text-decoration: underline;
}

.reference-link:hover {
  text-decoration: none;
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
  
  .action-bar {
    flex-direction: column;
    align-items: stretch;
  }
  
  .search-box {
    min-width: 100%;
  }
  
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .modal {
    max-width: 100%;
    max-height: 95vh;
  }
  
  .modal-medium,
  .modal-large,
  .modal-xlarge {
    width: 100%;
  }
  
  .vulnerability-header,
  .secret-header,
  .config-issue-header {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .vulnerability-package,
  .secret-filename,
  .config-issue-category {
    margin-left: 0;
  }
}
</style>
