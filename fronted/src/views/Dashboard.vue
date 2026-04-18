<template>
  <div class="dashboard">
    <header class="header">
      <div class="container">
        <div class="header-content">
          <div class="logo">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
            </svg>
            <div>
              <h1>Docker 日志查看器</h1>
              <p>资源监控 Dashboard</p>
            </div>
          </div>
          <div class="header-actions">
            <router-link to="/" class="btn btn-outline">
              容器列表
            </router-link>
            <button class="btn btn-outline" @click="refreshData">
              刷新
            </button>
            <label class="checkbox-label">
              <input
                type="checkbox"
                v-model="showAll"
                @change="fetchStats"
              />
              <span>显示全部容器</span>
            </label>
          </div>
        </div>
      </div>
    </header>

    <main class="main-content">
      <div class="container">
        <div v-if="error" class="error-message">
          {{ error }}
        </div>

        <div v-if="loading && stats.length === 0" class="loading-state">
          <div class="loading-spinner"></div>
          <p>加载中...</p>
        </div>

        <template v-else>
          <div class="stats-summary">
            <div class="stat-card">
              <div class="stat-icon" style="background-color: var(--primary-color);">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
                  <line x1="8" y1="21" x2="16" y2="21" />
                  <line x1="12" y1="17" x2="12" y2="21" />
                </svg>
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ runtimeStats.total_count }}</div>
                <div class="stat-label">总容器数</div>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon" style="background-color: var(--success-color);">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
              </div>
              <div class="stat-content">
                <div class="stat-value" style="color: var(--success-color);">{{ runtimeStats.running_count }}</div>
                <div class="stat-label">运行中</div>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon" style="background-color: var(--error-color);">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="15" y1="9" x2="9" y2="15" />
                  <line x1="9" y1="9" x2="15" y2="15" />
                </svg>
              </div>
              <div class="stat-content">
                <div class="stat-value" style="color: var(--error-color);">{{ runtimeStats.stopped_count }}</div>
                <div class="stat-label">已停止</div>
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-icon" style="background-color: var(--warning-color);">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
              </div>
              <div class="stat-content">
                <div class="stat-value" style="color: var(--warning-color);">{{ runtimeStats.paused_count }}</div>
                <div class="stat-label">已暂停</div>
              </div>
            </div>
          </div>

          <div v-if="runtimeStats.runtime_stats && Object.keys(runtimeStats.runtime_stats).length > 0" class="card">
            <h2 class="card-title">运行时长统计</h2>
            <div class="runtime-stats">
              <div class="runtime-item">
                <span class="runtime-label">最短运行时间</span>
                <span class="runtime-value">{{ runtimeStats.runtime_stats.min_runtime_human }}</span>
              </div>
              <div class="runtime-item">
                <span class="runtime-label">最长运行时间</span>
                <span class="runtime-value">{{ runtimeStats.runtime_stats.max_runtime_human }}</span>
              </div>
              <div class="runtime-item">
                <span class="runtime-label">平均运行时间</span>
                <span class="runtime-value">{{ runtimeStats.runtime_stats.avg_runtime_human }}</span>
              </div>
            </div>
          </div>

          <div class="card">
            <h2 class="card-title">容器资源使用情况</h2>
            <div v-if="stats.length === 0" class="empty-state">
              暂无容器数据
            </div>
            <div v-else class="container-stats-grid">
              <div
                v-for="container in stats"
                :key="container.container_id"
                class="container-stat-card"
                :class="{ 'container-stopped': container.state !== 'running' }"
              >
                <div class="container-header">
                  <div class="container-info">
                    <div class="status-dot" :class="getStatusClass(container.state)"></div>
                    <div>
                      <h3 class="container-name">{{ container.container_name }}</h3>
                      <p class="container-image">{{ container.image }}</p>
                    </div>
                  </div>
                  <span class="badge" :class="container.state === 'running' ? 'badge-success' : 'badge-secondary'">
                    {{ container.state }}
                  </span>
                </div>

                <template v-if="container.state === 'running'">
                  <div class="resource-section">
                    <div class="resource-row">
                      <div class="resource-label">
                        <span>CPU</span>
                        <span class="resource-value">{{ container.cpu_percent }}%</span>
                      </div>
                      <div class="progress-bar">
                        <div
                          class="progress-fill cpu-progress"
                          :style="{ width: getProgressWidth(container.cpu_percent) }"
                        ></div>
                      </div>
                    </div>
                  </div>

                  <div class="resource-section">
                    <div class="resource-row">
                      <div class="resource-label">
                        <span>内存</span>
                        <span class="resource-value">
                          {{ formatBytes(container.memory_usage) }} / {{ formatBytes(container.memory_limit) }}
                          ({{ container.memory_percent }}%)
                        </span>
                      </div>
                      <div class="progress-bar">
                        <div
                          class="progress-fill memory-progress"
                          :style="{ width: getProgressWidth(container.memory_percent) }"
                        ></div>
                      </div>
                    </div>
                  </div>

                  <div class="network-section">
                    <div class="network-header">网络 I/O</div>
                    <div class="network-stats">
                      <div class="network-item">
                        <span class="network-icon rx">↓</span>
                        <div>
                          <div class="network-label">入站流量</div>
                          <div class="network-value">{{ formatBytes(container.network_rx_bytes) }}</div>
                        </div>
                      </div>
                      <div class="network-item">
                        <span class="network-icon tx">↑</span>
                        <div>
                          <div class="network-label">出站流量</div>
                          <div class="network-value">{{ formatBytes(container.network_tx_bytes) }}</div>
                        </div>
                      </div>
                    </div>
                    <div class="network-details">
                      <span>包: {{ container.network_rx_packets }} 收 / {{ container.network_tx_packets }} 发</span>
                      <span v-if="container.network_rx_errors > 0 || container.network_tx_errors > 0" class="error-text">
                        错误: {{ container.network_rx_errors }} 收 / {{ container.network_tx_errors }} 发
                      </span>
                    </div>
                  </div>

                  <div class="block-section">
                    <div class="block-header">磁盘 I/O</div>
                    <div class="block-stats">
                      <span class="block-item">
                        <span class="block-label">读:</span>
                        <span class="block-value">{{ formatBytes(container.block_read_bytes) }}</span>
                      </span>
                      <span class="block-item">
                        <span class="block-label">写:</span>
                        <span class="block-value">{{ formatBytes(container.block_write_bytes) }}</span>
                      </span>
                    </div>
                  </div>
                </template>

                <template v-else>
                  <div class="container-inactive">
                    <p>容器未运行，无法获取资源统计</p>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </template>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import axios from 'axios'

const stats = ref([])
const runtimeStats = ref({
  total_count: 0,
  running_count: 0,
  stopped_count: 0,
  paused_count: 0,
  runtime_stats: {}
})
const loading = ref(true)
const error = ref(null)
const showAll = ref(false)

let refreshInterval = null

const fetchStats = async () => {
  try {
    const response = await axios.get('/api/dashboard/stats', {
      params: { all_containers: showAll.value }
    })
    if (response.data.success) {
      stats.value = response.data.data
    }
  } catch (err) {
    console.error('获取统计信息失败:', err)
  }
}

const fetchRuntimeStats = async () => {
  try {
    const response = await axios.get('/api/dashboard/runtime', {
      params: { all_containers: true }
    })
    if (response.data.success) {
      runtimeStats.value = response.data.data
    }
  } catch (err) {
    console.error('获取运行时长统计失败:', err)
  }
}

const fetchData = async () => {
  try {
    loading.value = true
    error.value = null
    await Promise.all([fetchStats(), fetchRuntimeStats()])
  } catch (err) {
    error.value = err.message || '获取数据失败'
  } finally {
    loading.value = false
  }
}

const refreshData = () => {
  fetchData()
}

const formatBytes = (bytes) => {
  if (bytes === 0 || !bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const getStatusClass = (state) => {
  const classes = {
    running: 'status-running',
    exited: 'status-stopped',
    paused: 'status-paused'
  }
  return classes[state] || 'status-unknown'
}

const getProgressWidth = (percent) => {
  const clamped = Math.max(0, Math.min(100, percent))
  return clamped + '%'
}

onMounted(() => {
  fetchData()
  refreshInterval = setInterval(() => {
    fetchStats()
  }, 5000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<style scoped>
.dashboard {
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
  align-items: center;
  gap: 1rem;
}

.main-content {
  padding: 1.5rem 0;
}

.container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 1rem;
}

.error-message {
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  padding: 1rem;
  border-radius: 0.5rem;
  margin-bottom: 1rem;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem;
  color: var(--text-secondary);
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

.card {
  background-color: var(--bg-primary);
  border-radius: 0.75rem;
  padding: 1.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  margin-bottom: 1.5rem;
}

.card-title {
  font-size: 1.125rem;
  font-weight: 600;
  margin: 0 0 1rem 0;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--border-color);
}

.stats-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat-card {
  background-color: var(--bg-primary);
  border-radius: 0.75rem;
  padding: 1.25rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.stat-value {
  font-size: 1.75rem;
  font-weight: 700;
  line-height: 1;
}

.stat-label {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin-top: 0.25rem;
}

.runtime-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
}

.runtime-item {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.runtime-label {
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.runtime-value {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--text-primary);
}

.container-stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 1.5rem;
}

.container-stat-card {
  background-color: var(--bg-secondary);
  border-radius: 0.5rem;
  padding: 1rem;
  border: 1px solid var(--border-color);
}

.container-stat-card.container-stopped {
  opacity: 0.7;
}

.container-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--border-color);
}

.container-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.status-dot {
  width: 0.75rem;
  height: 0.75rem;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
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

.status-unknown {
  background-color: var(--text-secondary);
}

.container-name {
  font-size: 1rem;
  font-weight: 600;
  margin: 0;
}

.container-image {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin: 0;
  font-family: 'Courier New', monospace;
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

.resource-section {
  margin-bottom: 1rem;
}

.resource-row {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.resource-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.875rem;
}

.resource-value {
  font-weight: 500;
}

.progress-bar {
  height: 8px;
  background-color: var(--border-color);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

.cpu-progress {
  background: linear-gradient(90deg, #3b82f6, #60a5fa);
}

.memory-progress {
  background: linear-gradient(90deg, #8b5cf6, #a78bfa);
}

.network-section {
  margin-bottom: 1rem;
  padding: 0.75rem;
  background-color: rgba(59, 130, 246, 0.05);
  border-radius: 0.375rem;
}

.network-header {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 0.5rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.network-stats {
  display: flex;
  gap: 1.5rem;
}

.network-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.network-icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 0.75rem;
}

.network-icon.rx {
  background-color: rgba(16, 185, 129, 0.1);
  color: var(--success-color);
}

.network-icon.tx {
  background-color: rgba(239, 68, 68, 0.1);
  color: var(--error-color);
}

.network-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.network-value {
  font-size: 0.875rem;
  font-weight: 500;
}

.network-details {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-top: 0.5rem;
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.error-text {
  color: var(--error-color);
}

.block-section {
  padding: 0.75rem;
  background-color: rgba(245, 158, 11, 0.05);
  border-radius: 0.375rem;
}

.block-header {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 0.5rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.block-stats {
  display: flex;
  gap: 1.5rem;
}

.block-item {
  font-size: 0.875rem;
}

.block-label {
  color: var(--text-secondary);
}

.block-value {
  font-weight: 500;
}

.container-inactive {
  text-align: center;
  padding: 2rem;
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.empty-state {
  text-align: center;
  padding: 4rem 1rem;
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
}

.btn-outline {
  border: 1px solid var(--border-color);
}

.btn-outline:hover {
  background-color: var(--bg-secondary);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  cursor: pointer;
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

  .stats-summary {
    grid-template-columns: repeat(2, 1fr);
  }

  .container-stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>