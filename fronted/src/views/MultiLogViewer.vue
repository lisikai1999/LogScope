<template>
  <div class="log-viewer">
    <!-- Header -->
    <header class="header">
      <div class="container">
        <div class="header-content">
          <router-link to="/" class="back-link">
            ← 返回容器列表
          </router-link>
          <h1>多容器日志聚合</h1>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="main-content">
      <div class="container">
        <div class="card">
          <!-- Container Selection Panel -->
          <div class="container-selection">
            <h3 class="section-title">选择容器</h3>
            <div class="selection-controls">
              <div class="search-box">
                <input
                  type="text"
                  v-model="containerSearchQuery"
                  placeholder="搜索容器..."
                  class="input"
                />
              </div>
              <div class="selection-buttons">
                <button 
                  class="btn btn-sm" 
                  @click="toggleSelectAll"
                  :disabled="loadingContainers"
                >
                  {{ allSelected ? '取消全选' : '全选' }}
                </button>
                <button 
                  class="btn btn-sm" 
                  @click="clearSelection"
                  :disabled="loadingContainers"
                >
                  清除选择
                </button>
                <button 
                  class="btn btn-sm" 
                  @click="fetchContainers"
                  :disabled="loadingContainers"
                >
                  {{ loadingContainers ? '加载中...' : '刷新' }}
                </button>
              </div>
            </div>
            
            <!-- Loading State -->
            <div v-if="loadingContainers" class="selection-loading">
              加载容器列表...
            </div>
            
            <!-- Container Grid -->
            <div v-else class="container-grid">
              <div
                v-for="container in filteredContainers"
                :key="container.id"
                class="container-card"
                :class="{ 
                  'selected': selectedContainers.includes(container.id),
                  'container-card-running': container.state === 'running'
                }"
                @click="toggleContainer(container)"
              >
                <div class="container-status-indicator">
                  <span 
                    class="status-dot"
                    :class="getStatusClass(container.state)"
                  ></span>
                </div>
                <div class="container-info-select">
                  <div class="container-name">{{ getContainerName(container.names) }}</div>
                  <div class="container-meta">
                    <span class="container-id">{{ container.id.slice(0, 12) }}</span>
                    <span class="container-image">{{ container.image }}</span>
                  </div>
                </div>
                <div class="container-color" v-if="selectedContainers.includes(container.id)">
                  <span 
                    class="color-badge"
                    :style="{ backgroundColor: getContainerColor(container.id) }"
                  ></span>
                </div>
              </div>
            </div>
            
            <!-- Selection Summary -->
            <div class="selection-summary" v-if="selectedContainers.length > 0">
              <span>已选择 <strong>{{ selectedContainers.length }}</strong> 个容器</span>
              <div class="selected-containers-preview">
                <span 
                  v-for="id in selectedContainers" 
                  :key="id"
                  class="container-tag"
                  :style="{ backgroundColor: getContainerColor(id) }"
                >
                  {{ getSelectedContainerName(id) }}
                  <span class="tag-close" @click.stop="removeContainer(id)">×</span>
                </span>
              </div>
            </div>
          </div>

          <!-- Filters -->
          <div class="filters-section" v-if="selectedContainers.length > 0">
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
                  placeholder="100"
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
            <div class="filter-row">
              <div class="filter-group filter-group-full">
                <div class="search-label-row">
                  <label class="filter-label">搜索日志:</label>
                  <button
                    class="btn btn-sm btn-help"
                    @click="showSearchHelp = !showSearchHelp"
                    type="button"
                  >
                    {{ showSearchHelp ? '隐藏帮助' : '搜索语法帮助' }}
                  </button>
                </div>
                <div class="search-help-panel" v-if="showSearchHelp">
                  <div class="search-help-content">
                    <h4>高级搜索语法</h4>
                    <ul class="search-help-list">
                      <li><strong>简单搜索:</strong> <code>error</code> - 搜索包含 "error" 的日志</li>
                      <li><strong>正则表达式:</strong> <code>/error|warning/i</code> - 使用正则表达式搜索（i 表示不区分大小写）</li>
                      <li><strong>AND 组合:</strong> <code>error AND warning</code> 或 <code>error && warning</code> - 同时包含两个关键词</li>
                      <li><strong>OR 组合:</strong> <code>error OR warning</code> 或 <code>error || warning</code> - 包含任一关键词</li>
                      <li><strong>排除搜索:</strong> <code>-error</code> 或 <code>NOT error</code> - 排除包含 "error" 的日志</li>
                      <li><strong>组合示例:</strong> <code>(error OR warning) AND critical</code> - 包含 error 或 warning，且包含 critical</li>
                    </ul>
                  </div>
                </div>
                <div class="search-group">
                  <input
                    type="text"
                    v-model="searchQuery"
                    placeholder="输入关键词搜索... 支持正则、AND/OR 组合"
                    class="filter-input search-input"
                    @keyup.enter="fetchAllLogs"
                  />
                  <button
                    class="btn btn-primary"
                    @click="fetchAllLogs"
                    :disabled="loading || selectedContainers.length === 0"
                  >
                    搜索
                  </button>
                  <button
                    class="btn btn-outline"
                    @click="clearSearch"
                    v-if="searchQuery"
                  >
                    清除
                  </button>
                </div>
              </div>
            </div>
            <div class="filter-actions">
              <button
                class="btn btn-primary"
                @click="fetchAllLogs"
                :disabled="loading || selectedContainers.length === 0"
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
                {{ autoRefresh ? '停止自动刷新' : '开启自动刷新 (5s)' }}
              </button>
              <div class="export-group">
                <label class="filter-label">导出格式:</label>
                <select
                  v-model="exportFormat"
                  class="filter-input filter-input-select"
                >
                  <option value="json">JSON</option>
                  <option value="txt">TXT</option>
                  <option value="csv">CSV</option>
                </select>
                <button
                  class="btn btn-primary"
                  @click="exportLogs"
                  :disabled="exporting || mergedLogs.length === 0"
                >
                  {{ exporting ? '导出中...' : '导出日志' }}
                </button>
              </div>
            </div>
          </div>

          <!-- Empty Selection State -->
          <div v-else-if="!loadingContainers && selectedContainers.length === 0" class="empty-selection">
            <div class="empty-icon">📦</div>
            <h3>请选择要查看的容器</h3>
            <p>从上方容器列表中选择一个或多个容器，即可在统一视图中查看聚合日志</p>
            <div class="selection-tips">
              <div class="tip-item">
                <span class="tip-icon">💡</span>
                <span>点击容器卡片即可选中/取消选中</span>
              </div>
              <div class="tip-item">
                <span class="tip-icon">🎨</span>
                <span>每个选中的容器会分配唯一颜色，便于区分日志来源</span>
              </div>
              <div class="tip-item">
                <span class="tip-icon">⏱️</span>
                <span>日志将按时间顺序混合展示，方便追踪跨服务调用链</span>
              </div>
            </div>
          </div>

          <!-- Statistics Panel -->
          <MultiLogStatsPanel 
            :logs="mergedLogs" 
            :containers="containers"
            :selectedContainers="selectedContainers"
            :getContainerColor="getContainerColor"
            :getContainerName="getContainerNameFromId"
            v-if="selectedContainers.length > 0 && mergedLogs.length > 0" 
          />

          <!-- Error Message with Retry -->
          <div v-if="error" class="error-message">
            <div class="error-content">
              <span class="error-text">{{ error }}</span>
              <button class="btn btn-sm btn-error-retry" @click="retryFetch">
                重试
              </button>
            </div>
          </div>

          <!-- Logs Display -->
          <div 
            v-if="selectedContainers.length > 0"
            class="logs-container" 
            ref="logsContainerRef"
          >
            <!-- Initial Loading State -->
            <div v-if="loading && mergedLogs.length === 0" class="loading">
              <div v-for="i in 10" :key="i" class="skeleton"></div>
            </div>
            
            <!-- Empty State -->
            <div v-else-if="filteredLogs.length === 0 && !loading" class="empty-state">
              没有找到日志
            </div>
            
            <!-- Logs List -->
            <div v-else class="logs-list">
              <div
                v-for="(log, index) in filteredLogs"
                :key="`${log.containerId}-${log.timestamp}-${index}`"
                class="log-entry"
                :class="`log-${log.stream}`"
              >
                <div 
                  class="log-container-badge"
                  :style="{ backgroundColor: getContainerColor(log.containerId) }"
                >
                  {{ getContainerShortName(log.containerId) }}
                </div>
                <div class="log-timestamp">
                  {{ formatLogTime(log.timestamp) }}
                </div>
                <div class="log-stream">
                  {{ log.stream.toUpperCase() }}
                </div>
                <div class="log-message" v-html="highlightLogMessage(log)">
                </div>
              </div>
            </div>
          </div>
          
          <!-- Logs Footer -->
          <div class="logs-footer" v-if="selectedContainers.length > 0">
            <span>共 {{ filteredLogs.length }} 条日志 (来自 {{ selectedContainers.length }} 个容器)</span>
            <span v-if="autoRefresh" class="auto-refresh-indicator">
              (自动刷新中)
            </span>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import axios from 'axios'
import MultiLogStatsPanel from '../components/MultiLogStatsPanel.vue'

const containers = ref([])
const loadingContainers = ref(true)
const containerSearchQuery = ref('')

const selectedContainers = ref([])
const containerColors = ref({})

const logsByContainer = ref({})
const loading = ref(false)
const error = ref(null)
const logsContainerRef = ref(null)

const CONTAINER_COLORS = [
  '#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
  '#14b8a6', '#a855f7', '#eab308', '#22c55e', '#0ea5e9'
]

const PAGE_SIZE = 500
const MAX_RETRY_COUNT = 3

const sinceTime = ref('')
const untilTime = ref('')
const tailCount = ref(100)
const filterStdout = ref(true)
const filterStderr = ref(true)
const autoRefresh = ref(false)
const searchQuery = ref('')
const exportFormat = ref('json')
const exporting = ref(false)
const showSearchHelp = ref(false)

let refreshInterval = null
let retryCount = 0

const filteredContainers = computed(() => {
  if (!containerSearchQuery.value) {
    return containers.value
  }
  const query = containerSearchQuery.value.toLowerCase()
  return containers.value.filter(c => {
    const name = getContainerName(c.names)
    return name.toLowerCase().includes(query) ||
           c.image.toLowerCase().includes(query) ||
           c.id.toLowerCase().includes(query)
  })
})

const allSelected = computed(() => {
  return filteredContainers.value.length > 0 && 
         filteredContainers.value.every(c => selectedContainers.value.includes(c.id))
})

const mergedLogs = computed(() => {
  const allLogs = []
  for (const [containerId, logs] of Object.entries(logsByContainer.value)) {
    allLogs.push(...logs.map(log => ({ ...log, containerId })))
  }
  return allLogs.sort((a, b) => a.timestamp - b.timestamp)
})

const filteredLogs = computed(() => {
  return mergedLogs.value.filter(log => {
    if (log.stream === 'stdout' && !filterStdout.value) return false
    if (log.stream === 'stderr' && !filterStderr.value) return false
    return true
  })
})

const getContainerColor = (containerId) => {
  if (!containerColors.value[containerId]) {
    const index = selectedContainers.value.indexOf(containerId)
    containerColors.value[containerId] = CONTAINER_COLORS[index % CONTAINER_COLORS.length]
  }
  return containerColors.value[containerId]
}

const getContainerName = (names) => {
  if (!names || names.length === 0) return 'N/A'
  return names[0].replace(/^\//, '')
}

const getContainerNameFromId = (containerId) => {
  const container = containers.value.find(c => c.id === containerId)
  if (container) {
    return getContainerName(container.names)
  }
  return containerId.slice(0, 12)
}

const getContainerShortName = (containerId) => {
  const name = getContainerNameFromId(containerId)
  if (name.length > 8) {
    return name.slice(0, 6) + '..'
  }
  return name
}

const getSelectedContainerName = (containerId) => {
  return getContainerNameFromId(containerId)
}

const getStatusClass = (state) => {
  const classes = {
    running: 'status-running',
    exited: 'status-stopped',
    paused: 'status-paused'
  }
  return classes[state] || 'status-unknown'
}

const toggleContainer = (container) => {
  const index = selectedContainers.value.indexOf(container.id)
  if (index > -1) {
    removeContainer(container.id)
  } else {
    addContainer(container.id)
  }
}

const addContainer = (containerId) => {
  if (!selectedContainers.value.includes(containerId)) {
    selectedContainers.value.push(containerId)
  }
}

const removeContainer = (containerId) => {
  const index = selectedContainers.value.indexOf(containerId)
  if (index > -1) {
    selectedContainers.value.splice(index, 1)
    delete logsByContainer.value[containerId]
    delete containerColors.value[containerId]
  }
}

const toggleSelectAll = () => {
  if (allSelected.value) {
    clearSelection()
  } else {
    filteredContainers.value.forEach(c => {
      if (!selectedContainers.value.includes(c.id)) {
        selectedContainers.value.push(c.id)
      }
    })
  }
}

const clearSelection = () => {
  selectedContainers.value = []
  logsByContainer.value = {}
  containerColors.value = {}
}

const fetchContainers = async () => {
  try {
    loadingContainers.value = true
    const response = await axios.get('/api/containers', {
      params: { all_containers: true, page_size: 1000 }
    })
    
    if (response.data.success) {
      containers.value = response.data.data
    }
  } catch (err) {
    console.error('Error fetching containers:', err)
  } finally {
    loadingContainers.value = false
  }
}

const fetchLogsForContainer = async (containerId) => {
  try {
    const params = {}

    if (sinceTime.value) {
      params.since = Math.floor(new Date(sinceTime.value).getTime() / 1000)
    }
    if (untilTime.value) {
      params.until = Math.floor(new Date(untilTime.value).getTime() / 1000)
    }
    if (searchQuery.value) {
      params.search = searchQuery.value
    }
    
    const useLegacyTailMode = tailCount.value !== null
    
    if (useLegacyTailMode) {
      params.tail = tailCount.value
    } else {
      params.start_from_head = true
      params.limit = PAGE_SIZE
    }

    const response = await axios.get(
      `/api/containers/${containerId}/logs`,
      { params }
    )

    if (response.data.success) {
      logsByContainer.value[containerId] = response.data.data
    }
  } catch (err) {
    console.error(`Error fetching logs for container ${containerId}:`, err)
  }
}

const fetchAllLogs = async () => {
  if (selectedContainers.value.length === 0) {
    return
  }

  try {
    loading.value = true
    error.value = null
    retryCount = 0

    const promises = selectedContainers.value.map(id => fetchLogsForContainer(id))
    await Promise.all(promises)
    
    await nextTick()
    scrollToBottom()
    retryCount = 0
  } catch (err) {
    error.value = err.message || '获取日志失败'
    console.error('Fetch all logs error:', err)
  } finally {
    loading.value = false
  }
}

const fetchLogsAuto = async () => {
  if (selectedContainers.value.length === 0) return
  
  const promises = selectedContainers.value.map(async (containerId) => {
    try {
      const currentLogs = logsByContainer.value[containerId] || []
      if (currentLogs.length === 0) return
      
      const lastLogTimestamp = currentLogs[currentLogs.length - 1].timestamp
      
      const params = { since: lastLogTimestamp }

      const response = await axios.get(
        `/api/containers/${containerId}/logs`,
        { params }
      )

      if (response.data.success) {
        const newLogs = response.data.data
        
        if (newLogs.length > 0) {
          const existingIds = new Set(currentLogs.map(l => `${l.timestamp}-${l.message}`))
          const uniqueLogs = newLogs.filter(l => !existingIds.has(`${l.timestamp}-${l.message}`))
          
          if (uniqueLogs.length > 0) {
            const container = logsContainerRef.value
            const isAtBottom = container 
              ? container.scrollHeight - container.scrollTop <= container.clientHeight + 50
              : false
            
            logsByContainer.value[containerId] = [...currentLogs, ...uniqueLogs]
            
            if (isAtBottom) {
              await nextTick()
              scrollToBottom()
            }
          }
        }
      }
    } catch (err) {
      console.error(`Auto-refresh error for container ${containerId}:`, err)
    }
  })
  
  await Promise.all(promises)
}

const retryFetch = async () => {
  if (retryCount < MAX_RETRY_COUNT) {
    retryCount++
    error.value = null
    await fetchAllLogs()
  } else {
    error.value = `重试 ${MAX_RETRY_COUNT} 次后仍然失败，请稍后再试`
  }
}

const scrollToBottom = () => {
  if (logsContainerRef.value) {
    logsContainerRef.value.scrollTop = logsContainerRef.value.scrollHeight
  }
}

const scrollToTop = () => {
  if (logsContainerRef.value) {
    logsContainerRef.value.scrollTop = 0
  }
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
  fetchAllLogs()
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
  tailCount.value = 100
  filterStdout.value = true
  filterStderr.value = true
  searchQuery.value = ''
  fetchAllLogs()
}

const clearSearch = () => {
  searchQuery.value = ''
  fetchAllLogs()
}

const highlightLogMessage = (log) => {
  if (!log || !log.message) {
    return ''
  }
  
  const message = log.message
  const matches = log._matches
  
  if (!matches || matches.length === 0) {
    return escapeHtml(message)
  }
  
  const sortedMatches = [...matches].sort((a, b) => a[0] - b[0])
  
  const mergedMatches = []
  for (const match of sortedMatches) {
    if (mergedMatches.length === 0) {
      mergedMatches.push([...match])
    } else {
      const last = mergedMatches[mergedMatches.length - 1]
      if (match[0] <= last[1]) {
        last[1] = Math.max(last[1], match[1])
      } else {
        mergedMatches.push([...match])
      }
    }
  }
  
  let result = ''
  let lastIndex = 0
  
  for (const [start, end] of mergedMatches) {
    if (start > lastIndex) {
      result += escapeHtml(message.slice(lastIndex, start))
    }
    result += '<span class="search-highlight">' + escapeHtml(message.slice(start, end)) + '</span>'
    lastIndex = end
  }
  
  if (lastIndex < message.length) {
    result += escapeHtml(message.slice(lastIndex))
  }
  
  return result
}

const escapeHtml = (text) => {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

const exportLogs = async () => {
  try {
    exporting.value = true
    
    const dataToExport = mergedLogs.value.map(log => ({
      containerId: log.containerId,
      containerName: getContainerNameFromId(log.containerId),
      timestamp: log.timestamp,
      time: formatLogTime(log.timestamp),
      stream: log.stream,
      message: log.message
    }))
    
    let content, filename, mimeType
    
    switch (exportFormat.value) {
      case 'json':
        content = JSON.stringify(dataToExport, null, 2)
        filename = 'multi-container-logs.json'
        mimeType = 'application/json'
        break
      case 'csv':
        const headers = ['Container ID', 'Container Name', 'Time', 'Stream', 'Message']
        const csvRows = [headers.join(',')]
        dataToExport.forEach(log => {
          csvRows.push([
            `"${log.containerId}"`,
            `"${log.containerName}"`,
            `"${log.time}"`,
            `"${log.stream}"`,
            `"${log.message.replace(/"/g, '""')}"`
          ].join(','))
        })
        content = csvRows.join('\n')
        filename = 'multi-container-logs.csv'
        mimeType = 'text/csv'
        break
      case 'txt':
      default:
        const txtLines = dataToExport.map(log => 
          `[${log.time}] [${log.containerName}] [${log.stream.toUpperCase()}] ${log.message}`
        )
        content = txtLines.join('\n')
        filename = 'multi-container-logs.txt'
        mimeType = 'text/plain'
        break
    }
    
    const blob = new Blob([content], { type: mimeType })
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(downloadUrl)
    
    console.log(`Logs exported successfully as ${exportFormat.value}`)
  } catch (err) {
    console.error('Export logs error:', err)
    alert(`导出日志失败: ${err.message}`)
  } finally {
    exporting.value = false
  }
}

watch(autoRefresh, (newValue) => {
  if (newValue) {
    refreshInterval = setInterval(() => {
      fetchLogsAuto()
    }, 5000)
  } else {
    if (refreshInterval) {
      clearInterval(refreshInterval)
      refreshInterval = null
    }
  }
})

onMounted(() => {
  fetchContainers()
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

/* Container Selection Styles */
.container-selection {
  margin-bottom: 1.5rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.section-title {
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 1rem 0;
  color: var(--text-primary);
}

.selection-controls {
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  align-items: center;
}

.search-box {
  flex: 1;
  min-width: 250px;
}

.input {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: 0.375rem;
  font-size: 0.875rem;
}

.input:focus {
  outline: none;
  border-color: var(--primary-color);
}

.selection-buttons {
  display: flex;
  gap: 0.5rem;
}

.selection-loading {
  text-align: center;
  padding: 2rem;
  color: var(--text-secondary);
}

.container-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.75rem;
  max-height: 300px;
  overflow-y: auto;
  padding: 0.25rem;
}

.container-card {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  border: 2px solid var(--border-color);
  border-radius: 0.5rem;
  cursor: pointer;
  transition: all 0.2s;
  background-color: var(--bg-secondary);
}

.container-card:hover {
  border-color: var(--primary-color);
  background-color: var(--bg-primary);
}

.container-card.selected {
  border-color: var(--primary-color);
  background-color: rgba(59, 130, 246, 0.05);
}

.container-card-running {
  border-left-color: var(--success-color);
  border-left-width: 3px;
}

.container-status-indicator {
  display: flex;
  align-items: center;
}

.status-dot {
  width: 0.75rem;
  height: 0.75rem;
  border-radius: 50%;
  display: inline-block;
}

.status-running {
  background-color: var(--success-color);
}

.status-stopped {
  background-color: var(--error-color);
}

.status-paused {
  background-color: var(--warning-color);
}

.container-info-select {
  flex: 1;
  min-width: 0;
}

.container-name {
  font-weight: 500;
  font-size: 0.875rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-primary);
}

.container-meta {
  display: flex;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-top: 0.25rem;
}

.container-id {
  font-family: 'Courier New', monospace;
}

.container-image {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.container-color {
  display: flex;
  align-items: center;
}

.color-badge {
  width: 1rem;
  height: 1rem;
  border-radius: 50%;
  border: 2px solid white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.selection-summary {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px dashed var(--border-color);
}

.selection-summary span {
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.selected-containers-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.container-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.5rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  color: white;
  cursor: pointer;
}

.tag-close {
  font-size: 1rem;
  line-height: 1;
  opacity: 0.7;
}

.tag-close:hover {
  opacity: 1;
}

/* Empty Selection Styles */
.empty-selection {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--text-secondary);
}

.empty-icon {
  font-size: 4rem;
  margin-bottom: 1rem;
}

.empty-selection h3 {
  font-size: 1.25rem;
  margin-bottom: 0.5rem;
  color: var(--text-primary);
}

.empty-selection p {
  margin-bottom: 1.5rem;
}

.selection-tips {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-width: 500px;
  margin: 0 auto;
}

.tip-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  text-align: left;
  padding: 0.75rem;
  background-color: var(--bg-secondary);
  border-radius: 0.5rem;
}

.tip-icon {
  font-size: 1.25rem;
}

/* Filters Section */
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

.search-label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.25rem;
}

.btn-help {
  background-color: transparent;
  color: var(--primary-color);
  border-color: var(--primary-color);
}

.btn-help:hover {
  background-color: var(--primary-color);
  color: white;
}

.search-help-panel {
  background-color: #fef3c7;
  border: 1px solid #fcd34d;
  border-radius: 0.375rem;
  padding: 0.75rem 1rem;
  margin-bottom: 0.75rem;
}

.search-help-content h4 {
  margin: 0 0 0.5rem 0;
  font-size: 0.875rem;
  font-weight: 600;
  color: #92400e;
}

.search-help-list {
  margin: 0;
  padding-left: 1.25rem;
  font-size: 0.8125rem;
  color: #78350f;
}

.search-help-list li {
  margin-bottom: 0.25rem;
}

.search-help-list code {
  background-color: #fde68a;
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
  font-family: 'Courier New', monospace;
  font-size: 0.75rem;
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

.filter-group-full {
  width: 100%;
}

.search-group {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.search-input {
  flex: 1;
  min-width: 300px;
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
  flex-wrap: wrap;
  align-items: flex-end;
}

.export-group {
  display: flex;
  align-items: flex-end;
  gap: 0.5rem;
  margin-left: auto;
}

.filter-input-select {
  min-width: 100px;
  background-color: var(--bg-primary);
  cursor: pointer;
}

.filter-input-select:focus {
  outline: none;
  border-color: var(--primary-color);
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

.btn-error-retry {
  background-color: var(--error-color);
  color: white;
  border-color: var(--error-color);
}

.btn-error-retry:hover {
  background-color: #dc2626;
}

.error-message {
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  padding: 1rem;
  border-radius: 0.5rem;
  margin-bottom: 1rem;
}

.error-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.error-text {
  flex: 1;
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
  gap: 0.75rem;
  padding: 0.5rem 1rem;
  border-bottom: 1px solid #2d2d2d;
  color: #d4d4d4;
  align-items: flex-start;
}

.log-entry:last-child {
  border-bottom: none;
}

.log-entry:hover {
  background-color: #2d2d2d;
}

.log-container-badge {
  min-width: 80px;
  padding: 0.125rem 0.5rem;
  border-radius: 0.25rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: white;
  text-align: center;
  white-space: nowrap;
  flex-shrink: 0;
}

.log-timestamp {
  color: #888;
  min-width: 180px;
  white-space: nowrap;
  flex-shrink: 0;
}

.log-stream {
  min-width: 70px;
  font-weight: bold;
  flex-shrink: 0;
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

:deep(.search-highlight) {
  background-color: #fbbf24;
  color: #1e1e1e;
  padding: 0 2px;
  border-radius: 2px;
  font-weight: bold;
}

.logs-footer {
  padding: 0.75rem 1rem;
  background-color: #2d2d2d;
  color: #888;
  font-size: 0.875rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px solid #3d3d3d;
}

.has-more-indicator {
  color: var(--primary-color);
  font-size: 0.75rem;
}

.auto-refresh-indicator {
  color: var(--success-color);
  font-size: 0.75rem;
}

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

.container-grid::-webkit-scrollbar {
  width: 6px;
}

.container-grid::-webkit-scrollbar-track {
  background: var(--bg-secondary);
  border-radius: 3px;
}

.container-grid::-webkit-scrollbar-thumb {
  background: var(--text-secondary);
  border-radius: 3px;
}

.container-grid::-webkit-scrollbar-thumb:hover {
  background: var(--text-primary);
}
</style>
