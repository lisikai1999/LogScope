<template>
  <div class="log-viewer">
    <!-- Header -->
    <header class="header">
      <div class="container">
        <div class="header-content">
          <router-link to="/" class="back-link">
            ← 返回容器列表
          </router-link>
          <h1>容器日志</h1>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="main-content">
      <div class="container">
        <div class="card">
          <!-- Container Info -->
          <div v-if="containerInfo" class="container-info">
            <h2>{{ getContainerName(containerInfo.names) }}</h2>
            <div class="info-items">
              <span class="info-item">
                <strong>镜像:</strong> {{ containerInfo.image }}
              </span>
              <span class="info-item">
                <strong>ID:</strong> {{ containerId.slice(0, 12) }}
              </span>
              <span class="info-item">
                <strong>状态:</strong>
                <span
                  class="badge"
                  :class="containerInfo.state === 'running' ? 'badge-success' : 'badge-secondary'"
                >
                  {{ containerInfo.status }}
                </span>
              </span>
            </div>
          </div>

          <!-- Filters -->
          <div class="filters-section">
            <div class="filter-row">
              <div class="filter-group">
                <label class="filter-label">开始时间:</label>
                <input
                  type="datetime-local"
                  v-model="sinceTime"
                  class="filter-input"
                />
              </div>
              <div class="filter-group">
                <label class="filter-label">结束时间:</label>
                <input
                  type="datetime-local"
                  v-model="untilTime"
                  class="filter-input"
                />
              </div>
              <div class="filter-group">
                <label class="filter-label">日志行数:</label>
                <input
                  type="number"
                  v-model.number="tailCount"
                  placeholder="全部"
                  min="1"
                  class="filter-input filter-input-number"
                />
              </div>
            </div>
            <div class="filter-row">
              <div class="filter-group">
                <label class="filter-label">快速选择:</label>
                <div class="quick-select">
                  <button
                    class="btn btn-sm"
                    @click="setTimeRange('last1h')"
                  >
                    最近1小时
                  </button>
                  <button
                    class="btn btn-sm"
                    @click="setTimeRange('last24h')"
                  >
                    最近24小时
                  </button>
                  <button
                    class="btn btn-sm"
                    @click="setTimeRange('last7d')"
                  >
                    最近7天
                  </button>
                  <button
                    class="btn btn-sm"
                    @click="setTimeRange('all')"
                  >
                    全部
                  </button>
                </div>
              </div>
              <div class="filter-group">
                <label class="filter-label">筛选:</label>
                <div class="checkbox-group">
                  <label class="checkbox-label">
                    <input
                      type="checkbox"
                      v-model="filterStdout"
                    />
                    <span>标准输出</span>
                  </label>
                  <label class="checkbox-label">
                    <input
                      type="checkbox"
                      v-model="filterStderr"
                    />
                    <span>错误输出</span>
                  </label>
                </div>
              </div>
            </div>
            <div class="filter-actions">
              <button
                class="btn btn-primary"
                @click="fetchLogs"
                :disabled="loading"
              >
                {{ loading ? '加载中...' : '查询日志' }}
              </button>
              <button
                class="btn btn-outline"
                @click="clearFilters"
              >
                清除筛选
              </button>
              <button
                class="btn btn-outline"
                @click="autoRefresh = !autoRefresh"
                :class="{ active: autoRefresh }"
              >
                {{ autoRefresh ? '停止自动刷新' : '开启自动刷新 (1s)' }}
              </button>
            </div>
          </div>

          <!-- Error Message -->
          <div v-if="error" class="error-message">
            {{ error }}
          </div>

          <!-- Logs Display -->
          <div class="logs-container">
            <div v-if="loading" class="loading">
              <div v-for="i in 10" :key="i" class="skeleton"></div>
            </div>
            <div v-else-if="filteredLogs.length === 0" class="empty-state">
              没有找到日志
            </div>
            <div v-else class="logs-list">
              <div
                v-for="(log, index) in filteredLogs"
                :key="index"
                class="log-entry"
                :class="`log-${log.stream}`"
              >
                <div class="log-timestamp">
                  {{ formatLogTime(log.timestamp) }}
                </div>
                <div class="log-stream">
                  {{ log.stream.toUpperCase() }}
                </div>
                <div class="log-message">
                  {{ log.message }}
                </div>
              </div>
            </div>
            <div class="logs-footer">
              共 {{ filteredLogs.length }} 条日志
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const containerId = ref(route.params.id)

const containerInfo = ref(null)
const logs = ref([])
const loading = ref(true)
const error = ref(null)

// 筛选条件
const sinceTime = ref('')
const untilTime = ref('')
const tailCount = ref(null)
const filterStdout = ref(true)
const filterStderr = ref(true)
const autoRefresh = ref(false)

// 追踪最后一条日志的时间戳，用于增量查询
let lastLogTimestamp = 0

let refreshInterval = null

const filteredLogs = computed(() => {
  return logs.value.filter(log => {
    if (log.stream === 'stdout' && !filterStdout.value) return false
    if (log.stream === 'stderr' && !filterStderr.value) return false
    return true
  })
})

const fetchContainerInfo = async () => {
  try {
    const response = await axios.get(`/api/containers/${containerId.value}`)
    if (response.data.success) {
      containerInfo.value = response.data.data
    }
  } catch (err) {
    console.error('Error fetching container info:', err)
  }
}

const fetchLogs = async () => {
  try {
    loading.value = true
    logs.value = []
    lastLogTimestamp = 0
    error.value = null

    const params = {}

    // 转换时间戳
    if (sinceTime.value) {
      params.since = Math.floor(new Date(sinceTime.value).getTime() / 1000)
    }
    if (untilTime.value) {
      params.until = Math.floor(new Date(untilTime.value).getTime() / 1000)
    }
    if (tailCount.value) {
      params.tail = tailCount.value
    }
    // 如果没有设置任何过滤条件，获取最后 100 行
    if (!sinceTime.value && !untilTime.value && !tailCount.value) {
      params.tail = 100
    }

    console.log('Manual query params:', params)

    const response = await axios.get(
      `/api/containers/${containerId.value}/logs`,
      { params }
    )

    if (response.data.success) {
      logs.value = response.data.data
      if (logs.value.length > 0) {
        lastLogTimestamp = logs.value[logs.value.length - 1].timestamp
      }
    } else {
      error.value = response.data.error || '获取日志失败'
    }
  } catch (err) {
    error.value = err.message || '获取日志失败'
  } finally {
    loading.value = false
  }
}

const fetchLogsAuto = async () => {
  try {
    if (lastLogTimestamp === 0) return
    
    const params = { since: lastLogTimestamp }

    const response = await axios.get(
      `/api/containers/${containerId.value}/logs`,
      { params }
    )

    if (response.data.success) {
      const newLogs = response.data.data
      
      if (logs.value.length > 0) {
        // 增量追加（避免重复）
        const existingIds = new Set(logs.value.map(l => `${l.timestamp}-${l.message}`))
        const uniqueLogs = newLogs.filter(l => !existingIds.has(`${l.timestamp}-${l.message}`))
        if (uniqueLogs.length > 0) {
          logs.value.push(...uniqueLogs)
          lastLogTimestamp = uniqueLogs[uniqueLogs.length - 1].timestamp
        }
      }
    }
  } catch (err) {
    console.error('Auto-refresh error:', err)
  }
}

const getContainerName = (names) => {
  if (!names || names.length === 0) return 'N/A'
  return names[0].replace(/^\//, '')
}

const formatLogTime = (timestamp) => {
  const date = new Date(timestamp * 1000)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  })
}

const setTimeRange = (range) => {
  const now = new Date()
  untilTime.value = formatDateTimeLocal(now)

  switch (range) {
    case 'last1h':
      sinceTime.value = formatDateTimeLocal(new Date(now.getTime() - 60 * 60 * 1000))
      break
    case 'last24h':
      sinceTime.value = formatDateTimeLocal(new Date(now.getTime() - 24 * 60 * 60 * 1000))
      break
    case 'last7d':
      sinceTime.value = formatDateTimeLocal(new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000))
      break
    case 'all':
      sinceTime.value = ''
      untilTime.value = ''
      break
  }

  tailCount.value = null
  fetchLogs(false)
}

const formatDateTimeLocal = (date) => {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day}T${hours}:${minutes}`
}

const clearFilters = () => {
  sinceTime.value = ''
  untilTime.value = ''
  tailCount.value = null
  filterStdout.value = true
  filterStderr.value = true
  fetchLogs()
}

// 自动刷新
watch(autoRefresh, (newValue) => {
  if (newValue) {
    refreshInterval = setInterval(() => {
      fetchLogsAuto()  // 调用自动刷新函数
    }, 5000)
  } else {
    if (refreshInterval) {
      clearInterval(refreshInterval)
      refreshInterval = null
    }
  }
})

onMounted(() => {
  fetchContainerInfo()
  fetchLogs()
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<style scoped>
.log-viewer {
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
  gap: 1rem;
}

.back-link {
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.875rem;
  white-space: nowrap;
}

.back-link:hover {
  color: var(--primary-color);
}

.header h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
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

.container-info {
  margin-bottom: 1.5rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.container-info h2 {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0 0 0.75rem 0;
}

.info-items {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  font-size: 0.875rem;
}

.info-item {
  color: var(--text-secondary);
}

.info-item strong {
  color: var(--text-primary);
  margin-right: 0.25rem;
}

.badge {
  display: inline-block;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
}

.badge-success {
  background-color: var(--success-color);
  color: white;
}

.badge-secondary {
  background-color: var(--text-secondary);
  color: white;
}

.filters-section {
  margin-bottom: 1.5rem;
  padding: 1rem;
  background-color: var(--bg-secondary);
  border-radius: 0.5rem;
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 1rem;
  align-items: flex-end;
}

.filter-row:last-child {
  margin-bottom: 0;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.filter-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-primary);
}

.filter-input {
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  font-size: 0.875rem;
  min-width: 200px;
}

.filter-input:focus {
  outline: none;
  border-color: var(--primary-color);
}

.filter-input-number {
  min-width: 100px;
}

.quick-select {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.checkbox-group {
  display: flex;
  gap: 1rem;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  cursor: pointer;
}

.filter-actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-color);
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
  border: 1px solid var(--border-color);
  background-color: var(--bg-primary);
  color: var(--text-primary);
  transition: all 0.2s;
}

.btn:hover:not(:disabled) {
  background-color: var(--bg-secondary);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background-color: var(--primary-color);
  color: white;
  border-color: var(--primary-color);
}

.btn-primary:hover:not(:disabled) {
  background-color: #2563eb;
}

.btn-outline {
  background-color: transparent;
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
}

.btn.active {
  background-color: var(--success-color);
  color: white;
  border-color: var(--success-color);
}

.error-message {
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  padding: 1rem;
  border-radius: 0.5rem;
  margin-bottom: 1rem;
}

.logs-container {
  background-color: #1e1e1e;
  border-radius: 0.5rem;
  overflow: hidden;
  max-height: 600px;
  overflow-y: auto;
}

.loading {
  padding: 1rem;
}

.skeleton {
  height: 2rem;
  background-color: #2d2d2d;
  border-radius: 0.25rem;
  margin-bottom: 0.5rem;
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.empty-state {
  padding: 4rem 1rem;
  text-align: center;
  color: #888;
}

.logs-list {
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
}

.log-entry {
  display: flex;
  gap: 1rem;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid #2d2d2d;
  color: #d4d4d4;
}

.log-entry:last-child {
  border-bottom: none;
}

.log-entry:hover {
  background-color: #2d2d2d;
}

.log-timestamp {
  color: #888;
  min-width: 180px;
  white-space: nowrap;
}

.log-stream {
  min-width: 70px;
  font-weight: bold;
}

.log-stdout .log-stream {
  color: var(--success-color);
}

.log-stderr .log-stream {
  color: var(--error-color);
}

.log-message {
  flex: 1;
  word-break: break-word;
}

.logs-footer {
  padding: 0.75rem 1rem;
  background-color: #2d2d2d;
  color: #888;
  font-size: 0.875rem;
  text-align: right;
  border-top: 1px solid #3d3d3d;
}

/* 滚动条样式 */
.logs-container::-webkit-scrollbar {
  width: 8px;
}

.logs-container::-webkit-scrollbar-track {
  background: #1e1e1e;
}

.logs-container::-webkit-scrollbar-thumb {
  background: #555;
  border-radius: 4px;
}

.logs-container::-webkit-scrollbar-thumb:hover {
  background: #666;
}
</style>
