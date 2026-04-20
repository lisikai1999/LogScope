<template>
  <div class="alert-rules">
    <header class="header">
      <div class="container">
        <div class="header-content">
          <div class="logo">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div>
              <h1>告警规则管理</h1>
              <p>配置日志告警规则和通知方式</p>
            </div>
          </div>
          <div class="header-actions">
            <router-link to="/" class="btn btn-outline">
              返回容器列表
            </router-link>
            <button class="btn btn-primary" @click="showCreateModal = true">
              + 创建规则
            </button>
          </div>
        </div>
      </div>
    </header>

    <main class="main-content">
      <div class="container">
        <div class="tabs">
          <button class="tab-btn" :class="{ active: activeTab === 'rules' }" @click="activeTab = 'rules'">
            告警规则 ({{ rules.length }})
          </button>
          <button class="tab-btn" :class="{ active: activeTab === 'alerts' }" @click="activeTab = 'alerts'">
            告警事件 ({{ alerts.length }})
          </button>
        </div>

        <div v-show="activeTab === 'rules'">
          <div v-if="loading" class="loading">
            <div v-for="i in 3" :key="i" class="skeleton"></div>
          </div>

          <div v-else-if="rules.length === 0" class="empty-state">
            <svg class="empty-icon" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <h3>暂无告警规则</h3>
            <p>创建告警规则来监控日志中的异常情况</p>
            <button class="btn btn-primary" @click="showCreateModal = true">
              创建第一个规则
            </button>
          </div>

          <div v-else class="rules-list">
            <div v-for="rule in rules" :key="rule.id" class="rule-card">
              <div class="rule-header">
                <div class="rule-title">
                  <span class="status-dot" :class="rule.enabled ? 'status-enabled' : 'status-disabled'"></span>
                  <h3>{{ rule.name }}</h3>
                </div>
                <div class="rule-actions">
                  <button class="btn btn-ghost btn-sm" @click="toggleRule(rule)" :title="rule.enabled ? '禁用' : '启用'">
                    {{ rule.enabled ? '禁用' : '启用' }}
                  </button>
                  <button class="btn btn-ghost btn-sm" @click="editRule(rule)">
                    编辑
                  </button>
                  <button class="btn btn-ghost btn-sm btn-danger" @click="confirmDelete(rule)">
                    删除
                  </button>
                </div>
              </div>
              
              <p class="rule-description">{{ rule.description || '暂无描述' }}</p>
              
              <div class="rule-meta">
                <span class="meta-item">
                  <strong>类型：</strong>{{ getRuleTypeLabel(rule.condition?.rule_type) }}
                </span>
                <span class="meta-item" v-if="rule.container_name || rule.container_id">
                  <strong>容器：</strong>{{ rule.container_name || rule.container_id?.slice(0, 12) }}
                </span>
                <span class="meta-item">
                  <strong>冷却：</strong>{{ formatCooldown(rule.cooldown_seconds) }}
                </span>
                <span class="meta-item" v-if="rule.last_triggered_at">
                  <strong>上次触发：</strong>{{ formatTime(rule.last_triggered_at) }}
                </span>
              </div>

              <div class="rule-notifications" v-if="rule.notifications?.length > 0">
                <span class="notification-label">通知方式：</span>
                <span v-for="n in rule.notifications" :key="n.channel_type" class="notification-badge" :class="{ disabled: !n.enabled }">
                  {{ getNotificationLabel(n.channel_type) }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div v-show="activeTab === 'alerts'">
          <div v-if="alertsLoading" class="loading">
            <div v-for="i in 5" :key="i" class="skeleton"></div>
          </div>

          <div v-else-if="alerts.length === 0" class="empty-state">
            <svg class="empty-icon" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h3>暂无告警事件</h3>
            <p>所有规则运行正常</p>
          </div>

          <div v-else class="alerts-list">
            <div v-for="alert in alerts" :key="alert.id" class="alert-item">
              <div class="alert-header">
                <span class="alert-status" :class="alert.status === 'active' ? 'status-active' : 'status-resolved'">
                  {{ alert.status === 'active' ? '🔴 触发' : '🟢 恢复' }}
                </span>
                <span class="alert-time">{{ formatTime(alert.triggered_at) }}</span>
              </div>
              <h4 class="alert-rule-name">{{ alert.rule_name }}</h4>
              <p class="alert-message">{{ alert.message }}</p>
              <div class="alert-meta">
                <span v-if="alert.container_name || alert.container_id">
                  容器：{{ alert.container_name || alert.container_id?.slice(0, 12) }}
                </span>
              </div>
              <div v-if="alert.matched_logs?.length > 0" class="alert-logs">
                <details>
                  <summary>查看匹配的日志 ({{ alert.matched_logs.length }})</summary>
                  <div class="log-list">
                    <div v-for="(log, index) in alert.matched_logs.slice(0, 10)" :key="index" class="log-item">
                      <span class="log-time">{{ formatLogTime(log.timestamp) }}</span>
                      <span class="log-stream" :class="log.stream">{{ log.stream?.toUpperCase() }}</span>
                      <span class="log-message">{{ log.message }}</span>
                    </div>
                  </div>
                </details>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <div v-if="showCreateModal || showEditModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="modal-header">
          <h2>{{ showEditModal ? '编辑告警规则' : '创建告警规则' }}</h2>
          <button class="modal-close" @click="closeModal">&times;</button>
        </div>

        <div class="modal-body">
          <form @submit.prevent="handleSubmit">
            <div class="form-group">
              <label class="form-label">规则名称 *</label>
              <input type="text" v-model="formData.name" class="form-input" placeholder="例如：ERROR 日志告警" required />
            </div>

            <div class="form-group">
              <label class="form-label">描述</label>
              <textarea v-model="formData.description" class="form-input" rows="2" placeholder="规则描述"></textarea>
            </div>

            <div class="form-group">
              <label class="form-label">应用容器</label>
              <select v-model="selectedContainerId" class="form-input">
                <option value="">所有容器</option>
                <option v-for="c in containers" :key="c.id" :value="c.id">
                  {{ getContainerName(c.names) }} ({{ c.id.slice(0, 12) }})
                </option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">规则类型 *</label>
              <select v-model="formData.condition.rule_type" class="form-input" required>
                <option value="consecutive_error">连续错误日志</option>
                <option value="keyword_frequency">关键词频率</option>
                <option value="level_count">日志级别计数</option>
                <option value="regex_match">正则表达式匹配</option>
              </select>
            </div>

            <div v-if="formData.condition.rule_type === 'consecutive_error'" class="condition-config">
              <div class="form-group">
                <label class="form-label">错误级别</label>
                <input type="text" v-model="formData.condition.level" class="form-input" placeholder="例如：ERROR、EXCEPTION、FATAL（留空则匹配所有错误关键词）" />
              </div>
              <div class="form-group">
                <label class="form-label">连续出现次数 *</label>
                <input type="number" v-model.number="formData.condition.count" class="form-input" min="1" required />
              </div>
            </div>

            <div v-if="formData.condition.rule_type === 'keyword_frequency'" class="condition-config">
              <div class="form-group">
                <label class="form-label">关键词 *</label>
                <input type="text" v-model="formData.condition.keyword" class="form-input" placeholder="例如：Failed to connect" required />
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">出现次数 *</label>
                  <input type="number" v-model.number="formData.condition.count" class="form-input" min="1" required />
                </div>
                <div class="form-group">
                  <label class="form-label">时间窗口（秒）*</label>
                  <input type="number" v-model.number="formData.condition.time_window_seconds" class="form-input" min="1" required />
                </div>
              </div>
              <label class="checkbox-label">
                <input type="checkbox" v-model="formData.condition.case_sensitive" />
                <span>区分大小写</span>
              </label>
            </div>

            <div v-if="formData.condition.rule_type === 'level_count'" class="condition-config">
              <div class="form-group">
                <label class="form-label">日志级别 *</label>
                <select v-model="formData.condition.level" class="form-input" required>
                  <option value="ERROR">ERROR</option>
                  <option value="WARN">WARN</option>
                  <option value="INFO">INFO</option>
                  <option value="DEBUG">DEBUG</option>
                  <option value="FATAL">FATAL</option>
                  <option value="EXCEPTION">EXCEPTION</option>
                </select>
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label class="form-label">出现次数 *</label>
                  <input type="number" v-model.number="formData.condition.count" class="form-input" min="1" required />
                </div>
                <div class="form-group">
                  <label class="form-label">时间窗口（秒）*</label>
                  <input type="number" v-model.number="formData.condition.time_window_seconds" class="form-input" min="1" required />
                </div>
              </div>
            </div>

            <div v-if="formData.condition.rule_type === 'regex_match'" class="condition-config">
              <div class="form-group">
                <label class="form-label">正则表达式 *</label>
                <input type="text" v-model="formData.condition.regex_pattern" class="form-input" placeholder="例如：error.*code\\s+\\d+" required />
              </div>
              <label class="checkbox-label">
                <input type="checkbox" v-model="formData.condition.case_sensitive" />
                <span>区分大小写</span>
              </label>
            </div>

            <div class="form-group">
              <label class="form-label">冷却时间（秒）</label>
              <input type="number" v-model.number="formData.cooldown_seconds" class="form-input" min="0" placeholder="默认 300 秒（5分钟）" />
              <p class="form-hint">触发告警后，在此时间内不会再次触发相同规则</p>
            </div>

            <div class="form-group">
              <label class="form-label">通知方式</label>
              <div class="notification-configs">
                <div v-for="(n, index) in formData.notifications" :key="index" class="notification-config">
                  <div class="notification-config-header">
                    <span class="notification-type">{{ getNotificationLabel(n.channel_type) }}</span>
                    <label class="checkbox-label">
                      <input type="checkbox" v-model="n.enabled" />
                      <span>启用</span>
                    </label>
                    <button type="button" class="btn btn-ghost btn-sm" @click="removeNotification(index)">删除</button>
                  </div>
                  <div v-if="n.channel_type === 'email'" class="notification-config-body">
                    <div class="form-group">
                      <label class="form-label">SMTP 服务器</label>
                      <input type="text" v-model="n.config.smtp_host" class="form-input" placeholder="例如：smtp.gmail.com" />
                    </div>
                    <div class="form-row">
                      <div class="form-group">
                        <label class="form-label">端口</label>
                        <input type="number" v-model.number="n.config.smtp_port" class="form-input" placeholder="587" />
                      </div>
                      <div class="form-group">
                        <label class="checkbox-label">
                          <input type="checkbox" v-model="n.config.use_tls" :checked="true" />
                          <span>使用 TLS</span>
                        </label>
                      </div>
                    </div>
                    <div class="form-group">
                      <label class="form-label">发件人邮箱</label>
                      <input type="email" v-model="n.config.sender_email" class="form-input" placeholder="sender@example.com" />
                    </div>
                    <div class="form-group">
                      <label class="form-label">发件人密码</label>
                      <input type="password" v-model="n.config.sender_password" class="form-input" placeholder="邮箱密码或应用专用密码" />
                    </div>
                    <div class="form-group">
                      <label class="form-label">收件人邮箱</label>
                      <input type="email" v-model="n.config.recipient_email" class="form-input" placeholder="recipient@example.com" />
                    </div>
                  </div>
                  <div v-if="n.channel_type === 'webhook'" class="notification-config-body">
                    <div class="form-group">
                      <label class="form-label">Webhook URL *</label>
                      <input type="url" v-model="n.config.url" class="form-input" placeholder="https://..." required />
                    </div>
                    <div class="form-group">
                      <label class="form-label">请求方法</label>
                      <select v-model="n.config.method" class="form-input">
                        <option value="POST">POST</option>
                        <option value="GET">GET</option>
                      </select>
                    </div>
                    <div class="form-group">
                      <label class="form-label">Payload 类型</label>
                      <select v-model="n.config.payload_type" class="form-input">
                        <option value="generic">通用 JSON</option>
                        <option value="dingtalk">钉钉</option>
                        <option value="wechat">企业微信</option>
                        <option value="slack">Slack</option>
                      </select>
                    </div>
                  </div>
                </div>
              </div>
              <div class="add-notification">
                <button type="button" class="btn btn-outline btn-sm" @click="addNotification('email')">
                  + 添加邮件通知
                </button>
                <button type="button" class="btn btn-outline btn-sm" @click="addNotification('webhook')">
                  + 添加 Webhook 通知
                </button>
              </div>
            </div>

            <div class="form-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="formData.enabled" />
                <span>立即启用规则</span>
              </label>
            </div>

            <div class="modal-footer">
              <button type="button" class="btn btn-outline" @click="closeModal">取消</button>
              <button type="submit" class="btn btn-primary">
                {{ showEditModal ? '保存修改' : '创建规则' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <div v-if="showDeleteConfirm" class="modal-overlay" @click.self="showDeleteConfirm = false">
      <div class="modal modal-small">
        <div class="modal-header">
          <h3>确认删除</h3>
        </div>
        <div class="modal-body">
          <p>确定要删除告警规则 "<strong>{{ ruleToDelete?.name }}</strong>" 吗？</p>
          <p class="text-warning">此操作不可撤销。</p>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="showDeleteConfirm = false">取消</button>
          <button class="btn btn-danger" @click="deleteRule">删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import axios from 'axios'

const activeTab = ref('rules')
const rules = ref([])
const alerts = ref([])
const containers = ref([])
const loading = ref(false)
const alertsLoading = ref(false)

const showCreateModal = ref(false)
const showEditModal = ref(false)
const showDeleteConfirm = ref(false)
const ruleToDelete = ref(null)
const editingRuleId = ref(null)

const selectedContainerId = ref('')

const defaultFormData = () => ({
  name: '',
  description: '',
  condition: {
    rule_type: 'keyword_frequency',
    level: '',
    count: 5,
    time_window_seconds: 60,
    keyword: '',
    regex_pattern: '',
    case_sensitive: false
  },
  notifications: [],
  enabled: true,
  cooldown_seconds: 300
})

const formData = ref(defaultFormData())

const fetchRules = async () => {
  try {
    loading.value = true
    const response = await axios.get('/api/alert-rules')
    if (response.data.success) {
      rules.value = response.data.data
    }
  } catch (err) {
    console.error('Failed to fetch rules:', err)
  } finally {
    loading.value = false
  }
}

const fetchAlerts = async () => {
  try {
    alertsLoading.value = true
    const response = await axios.get('/api/alerts', { params: { limit: 100 } })
    if (response.data.success) {
      alerts.value = response.data.data
    }
  } catch (err) {
    console.error('Failed to fetch alerts:', err)
  } finally {
    alertsLoading.value = false
  }
}

const fetchContainers = async () => {
  try {
    const response = await axios.get('/api/containers', { params: { all_containers: true, page_size: 100 } })
    if (response.data.success) {
      containers.value = response.data.data
    }
  } catch (err) {
    console.error('Failed to fetch containers:', err)
  }
}

const getContainerName = (names) => {
  if (!names || names.length === 0) return 'N/A'
  return names[0].replace(/^\//, '')
}

const getRuleTypeLabel = (type) => {
  const labels = {
    'consecutive_error': '连续错误',
    'keyword_frequency': '关键词频率',
    'level_count': '日志级别计数',
    'regex_match': '正则匹配'
  }
  return labels[type] || type
}

const getNotificationLabel = (type) => {
  const labels = {
    'email': '邮件',
    'webhook': 'Webhook'
  }
  return labels[type] || type
}

const formatCooldown = (seconds) => {
  if (seconds < 60) return `${seconds} 秒`
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟`
  return `${Math.floor(seconds / 3600)} 小时`
}

const formatTime = (timestamp) => {
  if (!timestamp) return 'N/A'
  return new Date(timestamp * 1000).toLocaleString('zh-CN')
}

const formatLogTime = (timestamp) => {
  if (!timestamp) return 'N/A'
  return new Date(timestamp * 1000).toLocaleTimeString('zh-CN')
}

const toggleRule = async (rule) => {
  try {
    const response = await axios.put(`/api/alert-rules/${rule.id}`, {
      enabled: !rule.enabled
    })
    if (response.data.success) {
      rule.enabled = !rule.enabled
    }
  } catch (err) {
    console.error('Failed to toggle rule:', err)
    alert('操作失败：' + (err.response?.data?.detail || err.message))
  }
}

const editRule = (rule) => {
  editingRuleId.value = rule.id
  selectedContainerId.value = rule.container_id || ''
  
  formData.value = {
    name: rule.name,
    description: rule.description || '',
    condition: {
      ...rule.condition
    },
    notifications: rule.notifications ? JSON.parse(JSON.stringify(rule.notifications)) : [],
    enabled: rule.enabled,
    cooldown_seconds: rule.cooldown_seconds || 300
  }
  
  showEditModal.value = true
}

const confirmDelete = (rule) => {
  ruleToDelete.value = rule
  showDeleteConfirm.value = true
}

const deleteRule = async () => {
  if (!ruleToDelete.value) return
  
  try {
    const response = await axios.delete(`/api/alert-rules/${ruleToDelete.value.id}`)
    if (response.data.success) {
      showDeleteConfirm.value = false
      ruleToDelete.value = null
      fetchRules()
    }
  } catch (err) {
    console.error('Failed to delete rule:', err)
    alert('删除失败：' + (err.response?.data?.detail || err.message))
  }
}

const closeModal = () => {
  showCreateModal.value = false
  showEditModal.value = false
  editingRuleId.value = null
  formData.value = defaultFormData()
  selectedContainerId.value = ''
}

const addNotification = (type) => {
  formData.value.notifications.push({
    channel_type: type,
    enabled: true,
    config: type === 'email' ? {
      smtp_host: '',
      smtp_port: 587,
      use_tls: true,
      sender_email: '',
      sender_password: '',
      recipient_email: ''
    } : {
      url: '',
      method: 'POST',
      payload_type: 'generic'
    }
  })
}

const removeNotification = (index) => {
  formData.value.notifications.splice(index, 1)
}

const handleSubmit = async () => {
  try {
    const submitData = {
      ...formData.value,
      container_id: selectedContainerId.value || null
    }
    
    let selectedContainer = containers.value.find(c => c.id === selectedContainerId.value)
    if (selectedContainer) {
      submitData.container_name = getContainerName(selectedContainer.names)
    }
    
    if (showEditModal.value && editingRuleId.value) {
      const response = await axios.put(`/api/alert-rules/${editingRuleId.value}`, submitData)
      if (response.data.success) {
        closeModal()
        fetchRules()
      }
    } else {
      const response = await axios.post('/api/alert-rules', submitData)
      if (response.data.success) {
        closeModal()
        fetchRules()
      }
    }
  } catch (err) {
    console.error('Failed to save rule:', err)
    alert('保存失败：' + (err.response?.data?.detail || err.message))
  }
}

watch(activeTab, (newTab) => {
  if (newTab === 'alerts') {
    fetchAlerts()
  }
})

onMounted(() => {
  fetchRules()
  fetchContainers()
})
</script>

<style scoped>
.alert-rules {
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

.logo {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.logo h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
}

.logo p {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin: 0;
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

.tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}

.tab-btn {
  padding: 0.5rem 1rem;
  border: 1px solid var(--border-color);
  background-color: var(--bg-primary);
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.875rem;
  transition: all 0.2s;
}

.tab-btn:hover {
  background-color: var(--bg-secondary);
}

.tab-btn.active {
  background-color: var(--primary-color);
  color: white;
  border-color: var(--primary-color);
}

.loading {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.skeleton {
  height: 8rem;
  background-color: var(--bg-secondary);
  border-radius: 0.5rem;
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.empty-state {
  text-align: center;
  padding: 4rem 1rem;
  color: var(--text-secondary);
}

.empty-icon {
  margin-bottom: 1rem;
  opacity: 0.5;
}

.empty-state h3 {
  margin-bottom: 0.5rem;
  color: var(--text-primary);
}

.empty-state p {
  margin-bottom: 1.5rem;
}

.rules-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.rule-card {
  background-color: var(--bg-primary);
  border-radius: 0.5rem;
  padding: 1.25rem;
  border: 1px solid var(--border-color);
}

.rule-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.75rem;
}

.rule-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.rule-title h3 {
  margin: 0;
  font-size: 1rem;
}

.status-dot {
  width: 0.75rem;
  height: 0.75rem;
  border-radius: 50%;
  display: inline-block;
}

.status-enabled {
  background-color: var(--success-color);
}

.status-disabled {
  background-color: var(--text-secondary);
}

.rule-actions {
  display: flex;
  gap: 0.5rem;
}

.rule-description {
  color: var(--text-secondary);
  font-size: 0.875rem;
  margin-bottom: 0.75rem;
}

.rule-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-bottom: 0.75rem;
}

.meta-item {
  display: inline-block;
}

.rule-notifications {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
}

.notification-label {
  color: var(--text-secondary);
}

.notification-badge {
  padding: 0.125rem 0.5rem;
  background-color: var(--primary-color);
  color: white;
  border-radius: 9999px;
  font-size: 0.75rem;
}

.notification-badge.disabled {
  background-color: var(--text-secondary);
  opacity: 0.5;
}

.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.alert-item {
  background-color: var(--bg-primary);
  border-radius: 0.5rem;
  padding: 1rem;
  border: 1px solid var(--border-color);
}

.alert-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.alert-status {
  font-weight: 600;
  font-size: 0.875rem;
}

.alert-status.status-active {
  color: var(--error-color);
}

.alert-status.status-resolved {
  color: var(--success-color);
}

.alert-time {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.alert-rule-name {
  margin: 0 0 0.25rem 0;
  font-size: 1rem;
}

.alert-message {
  margin: 0 0 0.5rem 0;
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.alert-meta {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-bottom: 0.75rem;
}

.alert-logs details {
  font-size: 0.75rem;
}

.alert-logs summary {
  cursor: pointer;
  color: var(--primary-color);
}

.log-list {
  margin-top: 0.5rem;
  padding: 0.75rem;
  background-color: var(--bg-secondary);
  border-radius: 0.25rem;
  font-family: monospace;
}

.log-item {
  display: flex;
  gap: 0.5rem;
  padding: 0.25rem 0;
  border-bottom: 1px solid var(--border-color);
}

.log-item:last-child {
  border-bottom: none;
}

.log-time {
  color: var(--text-secondary);
  white-space: nowrap;
}

.log-stream {
  font-weight: 600;
  padding: 0 0.25rem;
  border-radius: 0.125rem;
}

.log-stream.stdout {
  background-color: #dbeafe;
  color: #1e40af;
}

.log-stream.stderr {
  background-color: #fee2e2;
  color: #991b1b;
}

.log-message {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  z-index: 1000;
  padding: 1rem;
}

.modal {
  background-color: var(--bg-primary);
  border-radius: 0.75rem;
  max-width: 700px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-small {
  max-width: 400px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.25rem 1.25rem 0 1.25rem;
}

.modal-header h2,
.modal-header h3 {
  margin: 0;
  font-size: 1.25rem;
}

.modal-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 0;
  line-height: 1;
}

.modal-close:hover {
  color: var(--text-primary);
}

.modal-body {
  padding: 1.25rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-color);
}

.form-group {
  margin-bottom: 1rem;
}

.form-label {
  display: block;
  font-size: 0.875rem;
  font-weight: 500;
  margin-bottom: 0.375rem;
  color: var(--text-primary);
}

.form-input {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  font-size: 0.875rem;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  box-sizing: border-box;
}

.form-input:focus {
  outline: none;
  border-color: var(--primary-color);
}

.form-input::placeholder {
  color: var(--text-secondary);
}

.form-row {
  display: flex;
  gap: 1rem;
}

.form-row .form-group {
  flex: 1;
}

.form-hint {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-top: 0.25rem;
}

.text-warning {
  color: var(--warning-color);
}

.condition-config {
  background-color: var(--bg-secondary);
  padding: 1rem;
  border-radius: 0.375rem;
  margin-bottom: 1rem;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  cursor: pointer;
}

.notification-configs {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-bottom: 1rem;
}

.notification-config {
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  overflow: hidden;
}

.notification-config-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem;
  background-color: var(--bg-secondary);
}

.notification-type {
  font-weight: 600;
}

.notification-config-body {
  padding: 1rem;
}

.add-notification {
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
}

.btn-primary {
  background-color: var(--primary-color);
  color: white;
}

.btn-primary:hover {
  opacity: 0.9;
}

.btn-outline {
  border: 1px solid var(--border-color);
}

.btn-outline:hover {
  background-color: var(--bg-secondary);
}

.btn-ghost {
  background-color: transparent;
}

.btn-ghost:hover {
  background-color: var(--bg-secondary);
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
}

.btn-danger {
  background-color: var(--error-color);
  color: white;
}

.btn-danger:hover {
  opacity: 0.9;
}
</style>
