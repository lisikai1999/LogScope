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
                <label class="filter-label">搜索日志:</label>
                <div class="search-group">
                  <input
                    type="text"
                    v-model="searchQuery"
                    placeholder="输入关键词搜索日志内容..."
                    class="filter-input search-input"
                    @keyup.enter="fetchLogs"
                  />
                  <button
                    class="btn btn-primary"
                    @click="fetchLogs"
                    :disabled="loading"
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
            class="logs-container" 
            ref="logsContainerRef"
          >
            <!-- Initial Loading State -->
            <div v-if="loading && logs.length === 0" class="loading">
              <div v-for="i in 10" :key="i" class="skeleton"></div>
            </div>
            
            <!-- Empty State -->
            <div v-else-if="filteredLogs.length === 0 && !loading" class="empty-state">
              没有找到日志
            </div>
            
            <!-- Logs List -->
            <div v-else class="logs-list">
              <!-- Load Older Trigger (at top) -->
              <div ref="loadOlderTrigger" class="load-trigger">
                <div v-if="loadingOlder" class="loading-more">
                  <div class="loading-spinner"></div>
                  <span>加载更早的日志...</span>
                </div>
                <div v-else-if="!hasOlder && logs.length > 0" class="no-more-logs">
                  已加载全部历史日志
                </div>
              </div>
              
              <div
                v-for="(log, index) in filteredLogs"
                :key="`${log.timestamp}-${index}`"
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
              
              <!-- Load Newer Trigger (at bottom) -->
              <div ref="loadNewerTrigger" class="load-trigger">
                <div v-if="loadingNewer" class="loading-more">
                  <div class="loading-spinner"></div>
                  <span>加载更新的日志...</span>
                </div>
              </div>
            </div>
          </div>
          
          <!-- Logs Footer -->
          <div class="logs-footer">
            <span>共 {{ filteredLogs.length }} 条日志</span>
            <span v-if="hasNewer" class="has-more-indicator">
              (向下滚动加载更新的日志)
            </span>
            <span v-else-if="hasOlder" class="has-more-indicator">
              (向上滚动加载更早的日志)
            </span>
            <span v-else-if="autoRefresh" class="auto-refresh-indicator">
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
import { useRoute } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const containerId = ref(route.params.id)

const containerInfo = ref(null)
const logs = ref([])
const loading = ref(true)
const loadingOlder = ref(false)
const loadingNewer = ref(false)
const error = ref(null)
const hasOlder = ref(true)
const hasNewer = ref(false)
const logsContainerRef = ref(null)
const loadOlderTrigger = ref(null)
const loadNewerTrigger = ref(null)

const PAGE_SIZE = 1000
const MAX_RETRY_COUNT = 3

const sinceTime = ref('')
const untilTime = ref('')
const tailCount = ref(null)
const filterStdout = ref(true)
const filterStderr = ref(true)
const autoRefresh = ref(false)
const searchQuery = ref('')

let currentNextToken = null
let currentPrevToken = null
let refreshInterval = null
let olderObserver = null
let newerObserver = null
let retryCount = 0

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
    currentNextToken = null
    currentPrevToken = null
    error.value = null
    hasOlder.value = true
    hasNewer.value = false
    retryCount = 0

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

    console.log('Fetch logs params:', params)

    const response = await axios.get(
      `/api/containers/${containerId.value}/logs`,
      { params }
    )

    if (response.data.success) {
      logs.value = response.data.data
      
      if (useLegacyTailMode) {
        if (params.tail || params.limit) {
          hasOlder.value = response.data.has_more !== false
        } else {
          hasOlder.value = false
        }
        hasNewer.value = false
      } else {
        currentNextToken = response.data.next_token || null
        currentPrevToken = response.data.prev_token || null
        hasNewer.value = response.data.has_more_forward === true
        hasOlder.value = response.data.has_more_backward === true
      }
      
      await nextTick()
      if (useLegacyTailMode) {
        scrollToBottom()
      } else {
        scrollToTop()
      }
      
      retryCount = 0
    } else {
      error.value = response.data.error || '获取日志失败'
    }
  } catch (err) {
    error.value = err.message || '获取日志失败'
    console.error('Fetch logs error:', err)
  } finally {
    loading.value = false
  }
}

const fetchOlderLogs = async () => {
  if (loadingOlder.value || !hasOlder.value) {
    return
  }

  const useLegacyTailMode = tailCount.value !== null
  
  if (useLegacyTailMode) {
    const firstLogTimestamp = logs.value.length > 0 ? logs.value[0].timestamp : 0
    if (firstLogTimestamp === 0) return
    
    try {
      loadingOlder.value = true

      const params = {}
      
      if (sinceTime.value) {
        params.since = Math.floor(new Date(sinceTime.value).getTime() / 1000)
      }
      if (searchQuery.value) {
        params.search = searchQuery.value
      }
      
      params.until = firstLogTimestamp
      params.tail = PAGE_SIZE

      console.log('Fetch older logs (legacy) params:', params)

      const response = await axios.get(
        `/api/containers/${containerId.value}/logs`,
        { params }
      )

      if (response.data.success) {
        const olderLogs = response.data.data
        
        if (olderLogs.length > 0) {
          const existingIds = new Set(logs.value.map(l => `${l.timestamp}-${l.message}`))
          const uniqueLogs = olderLogs.filter(l => !existingIds.has(`${l.timestamp}-${l.message}`))
          
          if (uniqueLogs.length > 0) {
            const scrollTopBefore = logsContainerRef.value?.scrollTop || 0
            const scrollHeightBefore = logsContainerRef.value?.scrollHeight || 0
            
            logs.value = [...uniqueLogs, ...logs.value]
            
            await nextTick()
            
            if (logsContainerRef.value) {
              const scrollHeightAfter = logsContainerRef.value.scrollHeight
              const heightDiff = scrollHeightAfter - scrollHeightBefore
              logsContainerRef.value.scrollTop = scrollTopBefore + heightDiff
            }
          }
          
          hasOlder.value = response.data.has_more !== false && uniqueLogs.length > 0
        } else {
          hasOlder.value = false
        }
      }
    } catch (err) {
      console.error('Error fetching older logs:', err)
    } finally {
      loadingOlder.value = false
    }
    return
  }

  if (!currentPrevToken) {
    hasOlder.value = false
    return
  }

  try {
    loadingOlder.value = true

    const params = {
      next_token: currentPrevToken,
      direction: 'backward',
      limit: PAGE_SIZE
    }
    
    if (sinceTime.value) {
      params.since = Math.floor(new Date(sinceTime.value).getTime() / 1000)
    }
    if (untilTime.value) {
      params.until = Math.floor(new Date(untilTime.value).getTime() / 1000)
    }
    if (searchQuery.value) {
      params.search = searchQuery.value
    }

    console.log('Fetch older logs params:', params)

    const response = await axios.get(
      `/api/containers/${containerId.value}/logs`,
      { params }
    )

    if (response.data.success) {
      const olderLogs = response.data.data
      
      currentPrevToken = response.data.prev_token || null
      currentNextToken = response.data.next_token || null
      hasOlder.value = response.data.has_more_backward === true
      hasNewer.value = response.data.has_more_forward === true || hasNewer.value
      
      if (olderLogs.length > 0) {
        const existingIds = new Set(logs.value.map(l => `${l.timestamp}-${l.message}`))
        const uniqueLogs = olderLogs.filter(l => !existingIds.has(`${l.timestamp}-${l.message}`))
        
        if (uniqueLogs.length > 0) {
          const scrollTopBefore = logsContainerRef.value?.scrollTop || 0
          const scrollHeightBefore = logsContainerRef.value?.scrollHeight || 0
          
          logs.value = [...uniqueLogs, ...logs.value]
          
          await nextTick()
          
          if (logsContainerRef.value) {
            const scrollHeightAfter = logsContainerRef.value.scrollHeight
            const heightDiff = scrollHeightAfter - scrollHeightBefore
            logsContainerRef.value.scrollTop = scrollTopBefore + heightDiff
          }
        }
      }
    }
  } catch (err) {
    console.error('Error fetching older logs:', err)
  } finally {
    loadingOlder.value = false
  }
}

const fetchNewerLogs = async () => {
  if (loadingNewer.value) {
    return
  }

  const useLegacyTailMode = tailCount.value !== null
  
  if (useLegacyTailMode) {
    const lastLogTimestamp = logs.value.length > 0 ? logs.value[logs.value.length - 1].timestamp : 0
    if (lastLogTimestamp === 0) return
    
    try {
      loadingNewer.value = true

      const params = {
        since: lastLogTimestamp
      }

      if (untilTime.value) {
        params.until = Math.floor(new Date(untilTime.value).getTime() / 1000)
      }
      if (searchQuery.value) {
        params.search = searchQuery.value
      }

      const response = await axios.get(
        `/api/containers/${containerId.value}/logs`,
        { params }
      )

      if (response.data.success) {
        const newerLogs = response.data.data
        
        if (newerLogs.length > 0) {
          const existingIds = new Set(logs.value.map(l => `${l.timestamp}-${l.message}`))
          const uniqueLogs = newerLogs.filter(l => !existingIds.has(`${l.timestamp}-${l.message}`))
          
          if (uniqueLogs.length > 0) {
            const container = logsContainerRef.value
            const isAtBottom = container 
              ? container.scrollHeight - container.scrollTop <= container.clientHeight + 50
              : false
            
            logs.value = [...logs.value, ...uniqueLogs]
            
            if (isAtBottom) {
              await nextTick()
              scrollToBottom()
            }
          }
        }
      }
    } catch (err) {
      console.error('Error fetching newer logs:', err)
    } finally {
      loadingNewer.value = false
    }
    return
  }

  if (!currentNextToken) {
    hasNewer.value = false
    return
  }

  try {
    loadingNewer.value = true

    const params = {
      next_token: currentNextToken,
      direction: 'forward',
      limit: PAGE_SIZE
    }
    
    if (sinceTime.value) {
      params.since = Math.floor(new Date(sinceTime.value).getTime() / 1000)
    }
    if (untilTime.value) {
      params.until = Math.floor(new Date(untilTime.value).getTime() / 1000)
    }
    if (searchQuery.value) {
      params.search = searchQuery.value
    }

    console.log('Fetch newer logs params:', params)

    const response = await axios.get(
      `/api/containers/${containerId.value}/logs`,
      { params }
    )

    if (response.data.success) {
      const newerLogs = response.data.data
      
      currentNextToken = response.data.next_token || null
      currentPrevToken = response.data.prev_token || null
      hasNewer.value = response.data.has_more_forward === true
      hasOlder.value = response.data.has_more_backward === true || hasOlder.value
      
      if (newerLogs.length > 0) {
        const existingIds = new Set(logs.value.map(l => `${l.timestamp}-${l.message}`))
        const uniqueLogs = newerLogs.filter(l => !existingIds.has(`${l.timestamp}-${l.message}`))
        
        if (uniqueLogs.length > 0) {
          const container = logsContainerRef.value
          const isAtBottom = container 
            ? container.scrollHeight - container.scrollTop <= container.clientHeight + 50
            : false
          
          logs.value = [...logs.value, ...uniqueLogs]
          
          if (isAtBottom) {
            await nextTick()
            scrollToBottom()
          }
        }
      }
    }
  } catch (err) {
    console.error('Error fetching newer logs:', err)
  } finally {
    loadingNewer.value = false
  }
}

const fetchLogsAuto = async () => {
  try {
    if (logs.value.length === 0) return
    
    const lastLogTimestamp = logs.value[logs.value.length - 1].timestamp
    
    const params = { since: lastLogTimestamp }

    const response = await axios.get(
      `/api/containers/${containerId.value}/logs`,
      { params }
    )

    if (response.data.success) {
      const newLogs = response.data.data
      
      if (logs.value.length > 0) {
        const existingIds = new Set(logs.value.map(l => `${l.timestamp}-${l.message}`))
        const uniqueLogs = newLogs.filter(l => !existingIds.has(`${l.timestamp}-${l.message}`))
        if (uniqueLogs.length > 0) {
          const container = logsContainerRef.value
          const isAtBottom = container 
            ? container.scrollHeight - container.scrollTop <= container.clientHeight + 50
            : false
          
          logs.value.push(...uniqueLogs)
          
          if (isAtBottom) {
            await nextTick()
            scrollToBottom()
          }
        }
      }
    }
  } catch (err) {
    console.error('Auto-refresh error:', err)
  }
}

const retryFetch = async () => {
  if (retryCount < MAX_RETRY_COUNT) {
    retryCount++
    error.value = null
    await fetchLogs()
  } else {
    error.value = `重试 ${MAX_RETRY_COUNT} 次后仍然失败，请稍后再试`
  }
}

const setupObservers = () => {
  if (!window.IntersectionObserver) {
    return
  }

  if (olderObserver) {
    olderObserver.disconnect()
  }
  
  if (newerObserver) {
    newerObserver.disconnect()
  }

  if (loadOlderTrigger.value) {
    olderObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting && hasOlder.value && !loadingOlder.value) {
          fetchOlderLogs()
        }
      })
    }, {
      root: logsContainerRef.value,
      rootMargin: '100px',
      threshold: 0.1
    })
    olderObserver.observe(loadOlderTrigger.value)
  }

  if (loadNewerTrigger.value) {
    newerObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting && hasNewer.value && !loadingNewer.value && !autoRefresh.value) {
          fetchNewerLogs()
        }
      })
    }, {
      root: logsContainerRef.value,
      rootMargin: '100px',
      threshold: 0.1
    })
    newerObserver.observe(loadNewerTrigger.value)
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
  fetchLogs()
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
  searchQuery.value = ''
  fetchLogs()
}

const clearSearch = () => {
  searchQuery.value = ''
  fetchLogs()
}

watch(autoRefresh, (newValue) => {
  if (newValue) {
    refreshInterval = setInterval(() => {
      fetchLogsAuto()
    }, 1000)
  } else {
    if (refreshInterval) {
      clearInterval(refreshInterval)
      refreshInterval = null
    }
  }
})

watch([logs, hasOlder, hasNewer], () => {
  nextTick(() => {
    setupObservers()
  })
}, { deep: true })

onMounted(() => {
  fetchContainerInfo()
  fetchLogs()
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
  if (olderObserver) {
    olderObserver.disconnect()
  }
  if (newerObserver) {
    newerObserver.disconnect()
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

.load-trigger {
  min-height: 20px;
}

.loading-more {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 1rem;
  color: #888;
  font-size: 0.875rem;
}

.loading-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid #3d3d3d;
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.no-more-logs {
  text-align: center;
  padding: 0.75rem;
  color: #666;
  font-size: 0.75rem;
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
</style>
