<template>
  <div class="stats-panel">
    <div class="stats-header" @click="togglePanel">
      <span class="stats-title">
        <span class="icon">📊</span>
        多容器日志统计
      </span>
      <span class="toggle-icon">{{ isExpanded ? '▼' : '▶' }}</span>
    </div>
    
    <transition name="collapse">
      <div v-if="isExpanded" class="stats-content">
        <div class="stats-grid">
          <!-- Container Overview -->
          <div class="stats-card stats-card-full">
            <h3>容器概览</h3>
            <div class="container-overview">
              <div 
                v-for="id in selectedContainers" 
                :key="id"
                class="container-summary"
              >
                <div class="container-header">
                  <span 
                    class="color-badge"
                    :style="{ backgroundColor: getContainerColor(id) }"
                  ></span>
                  <span class="container-name">{{ getContainerName(id) }}</span>
                </div>
                <div class="container-stats">
                  <span class="stat-item">
                    <span class="stat-label">总日志:</span>
                    <span class="stat-value">{{ getContainerLogCount(id) }}</span>
                  </span>
                  <span class="stat-item">
                    <span class="stat-label">错误:</span>
                    <span class="stat-value error">{{ getContainerErrorCount(id) }}</span>
                  </span>
                  <span class="stat-item">
                    <span class="stat-label">警告:</span>
                    <span class="stat-value warn">{{ getContainerWarnCount(id) }}</span>
                  </span>
                </div>
              </div>
            </div>
          </div>
          
          <!-- Level Distribution -->
          <div class="stats-card">
            <h3>日志级别分布</h3>
            <div class="level-distribution">
              <div 
                v-for="(count, level) in levelStats" 
                :key="level" 
                class="level-item"
                :class="`level-${level.toLowerCase()}`"
              >
                <span class="level-name">{{ level }}</span>
                <span class="level-count">{{ count }}</span>
                <div class="level-bar">
                  <div 
                    class="level-bar-fill" 
                    :style="{ width: `${getLevelPercentage(level)}%` }"
                  ></div>
                </div>
              </div>
            </div>
            <div class="summary-text">
              共 <strong>{{ totalLogs }}</strong> 条日志
              <span v-if="errorRate > 0" class="error-rate">
                | 错误率: <strong :class="errorRate > 10 ? 'high' : ''">{{ errorRate.toFixed(2) }}%</strong>
              </span>
            </div>
          </div>
          
          <!-- Container Comparison -->
          <div class="stats-card">
            <h3>容器日志分布</h3>
            <div class="chart-container">
              <canvas ref="containerChartRef"></canvas>
            </div>
          </div>
          
          <!-- Error Rate Trend -->
          <div class="stats-card stats-card-full">
            <h3>错误率趋势 (最近10个时间点)</h3>
            <div class="chart-container">
              <canvas ref="trendChartRef"></canvas>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import {
  Chart,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  LineController,
  BarController,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'

Chart.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  LineController,
  BarController,
  Title,
  Tooltip,
  Legend,
  Filler
)

const props = defineProps({
  logs: {
    type: Array,
    default: () => []
  },
  containers: {
    type: Array,
    default: () => []
  },
  selectedContainers: {
    type: Array,
    default: () => []
  },
  getContainerColor: {
    type: Function,
    required: true
  },
  getContainerName: {
    type: Function,
    required: true
  }
})

const isExpanded = ref(true)
const trendChartRef = ref(null)
const containerChartRef = ref(null)
let trendChart = null
let containerChart = null

const logsByContainer = computed(() => {
  const grouped = {}
  props.selectedContainers.forEach(id => {
    grouped[id] = props.logs.filter(log => log.containerId === id)
  })
  return grouped
})

const levelStats = computed(() => {
  const stats = {
    ERROR: 0,
    WARN: 0,
    INFO: 0,
    DEBUG: 0,
    UNKNOWN: 0
  }
  
  props.logs.forEach(log => {
    const level = detectLogLevel(log.message)
    if (stats[level] !== undefined) {
      stats[level]++
    } else {
      stats.UNKNOWN++
    }
  })
  
  return stats
})

const totalLogs = computed(() => {
  return Object.values(levelStats.value).reduce((sum, count) => sum + count, 0)
})

const errorRate = computed(() => {
  if (totalLogs.value === 0) return 0
  return ((levelStats.value.ERROR + levelStats.value.WARN) / totalLogs.value) * 100
})

const maxLevelCount = computed(() => {
  const counts = Object.values(levelStats.value)
  return Math.max(...counts, 1)
})

function getContainerLogCount(containerId) {
  return logsByContainer.value[containerId]?.length || 0
}

function getContainerErrorCount(containerId) {
  const logs = logsByContainer.value[containerId] || []
  return logs.filter(log => {
    const level = detectLogLevel(log.message)
    return level === 'ERROR'
  }).length
}

function getContainerWarnCount(containerId) {
  const logs = logsByContainer.value[containerId] || []
  return logs.filter(log => {
    const level = detectLogLevel(log.message)
    return level === 'WARN'
  }).length
}

function detectLogLevel(message) {
  const upperMessage = message.toUpperCase()
  
  if (upperMessage.includes('ERROR') || upperMessage.includes('FATAL') || upperMessage.includes('CRITICAL') || upperMessage.includes('ERR]') || upperMessage.includes('ERROR:')) {
    return 'ERROR'
  }
  if (upperMessage.includes('WARN') || upperMessage.includes('WARNING') || upperMessage.includes('WARN]')) {
    return 'WARN'
  }
  if (upperMessage.includes('INFO') || upperMessage.includes('INFORMATION') || upperMessage.includes('INFO]')) {
    return 'INFO'
  }
  if (upperMessage.includes('DEBUG') || upperMessage.includes('TRACE') || upperMessage.includes('VERBOSE') || upperMessage.includes('DEBUG]')) {
    return 'DEBUG'
  }
  
  return 'UNKNOWN'
}

function getLevelPercentage(level) {
  if (maxLevelCount.value === 0) return 0
  return (levelStats.value[level] / maxLevelCount.value) * 100
}

function togglePanel() {
  isExpanded.value = !isExpanded.value
}

function initContainerChart() {
  if (!containerChartRef.value) return
  
  if (containerChart) {
    containerChart.destroy()
  }
  
  const ctx = containerChartRef.value.getContext('2d')
  if (!ctx) return
  
  const containerData = props.selectedContainers.map(id => ({
    name: props.getContainerName(id),
    color: props.getContainerColor(id),
    count: getContainerLogCount(id),
    errors: getContainerErrorCount(id),
    warns: getContainerWarnCount(id)
  }))
  
  const labels = containerData.map(d => d.name)
  const colors = containerData.map(d => d.color)
  const counts = containerData.map(d => d.count)
  const errors = containerData.map(d => d.errors)
  const warns = containerData.map(d => d.warns)
  
  containerChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [
        {
          label: '总日志',
          data: counts,
          backgroundColor: colors.map(c => c + '80'),
          borderColor: colors,
          borderWidth: 1
        },
        {
          label: '错误',
          data: errors,
          backgroundColor: '#ef444480',
          borderColor: '#ef4444',
          borderWidth: 1
        },
        {
          label: '警告',
          data: warns,
          backgroundColor: '#f59e0b80',
          borderColor: '#f59e0b',
          borderWidth: 1
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top',
          labels: {
            color: '#9ca3af',
            font: { size: 11 }
          }
        },
        tooltip: {
          mode: 'index',
          intersect: false
        }
      },
      scales: {
        x: {
          grid: {
            color: 'rgba(75, 85, 99, 0.3)'
          },
          ticks: {
            color: '#9ca3af',
            font: { size: 10 }
          }
        },
        y: {
          grid: {
            color: 'rgba(75, 85, 99, 0.3)'
          },
          ticks: {
            color: '#9ca3af',
            font: { size: 10 }
          },
          beginAtZero: true
        }
      }
    }
  })
}

function initTrendChart() {
  if (!trendChartRef.value) return
  
  if (trendChart) {
    trendChart.destroy()
  }
  
  const ctx = trendChartRef.value.getContext('2d')
  if (!ctx) return
  
  const trendData = calculateTrendData()
  
  const datasets = []
  
  props.selectedContainers.forEach(id => {
    const name = props.getContainerName(id)
    const color = props.getContainerColor(id)
    
    datasets.push({
      label: `${name} - 错误`,
      data: trendData.containerErrors[id] || [],
      borderColor: color,
      backgroundColor: color + '20',
      borderDash: [5, 5],
      fill: false,
      tension: 0.4
    })
    
    datasets.push({
      label: `${name} - 警告`,
      data: trendData.containerWarns[id] || [],
      borderColor: color,
      backgroundColor: color + '20',
      borderDash: [2, 2],
      fill: false,
      tension: 0.4
    })
  })
  
  datasets.push({
    label: '总体错误率',
    data: trendData.errorRates,
    borderColor: '#ef4444',
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    fill: true,
    tension: 0.4,
    yAxisID: 'y1'
  })
  
  trendChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: trendData.labels,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top',
          labels: {
            color: '#9ca3af',
            font: { size: 10 }
          }
        },
        tooltip: {
          mode: 'index',
          intersect: false
        }
      },
      scales: {
        x: {
          grid: {
            color: 'rgba(75, 85, 99, 0.3)'
          },
          ticks: {
            color: '#9ca3af',
            maxRotation: 45,
            minRotation: 45,
            font: { size: 10 }
          }
        },
        y: {
          grid: {
            color: 'rgba(75, 85, 99, 0.3)'
          },
          ticks: {
            color: '#9ca3af',
            font: { size: 10 }
          },
          beginAtZero: true
        },
        y1: {
          position: 'right',
          grid: {
            drawOnChartArea: false
          },
          ticks: {
            color: '#ef4444',
            font: { size: 10 },
            callback: function(value) {
              return value + '%'
            }
          },
          beginAtZero: true,
          max: 100
        }
      },
      interaction: {
        mode: 'nearest',
        axis: 'x',
        intersect: false
      }
    }
  })
}

function calculateTrendData() {
  const logs = [...props.logs]
  
  if (logs.length === 0) {
    return {
      labels: [],
      errorRates: [],
      containerErrors: {},
      containerWarns: {}
    }
  }
  
  const sortedLogs = logs.sort((a, b) => a.timestamp - b.timestamp)
  
  const startTime = sortedLogs[0].timestamp
  const endTime = sortedLogs[sortedLogs.length - 1].timestamp
  const totalDuration = endTime - startTime
  
  const numBuckets = 10
  const bucketDuration = totalDuration > 0 ? totalDuration / numBuckets : 1
  
  const buckets = Array(numBuckets).fill(null).map(() => ({
    total: 0,
    error: 0,
    warn: 0,
    containerErrors: {},
    containerWarns: {}
  }))
  
  props.selectedContainers.forEach(id => {
    buckets.forEach(b => {
      b.containerErrors[id] = 0
      b.containerWarns[id] = 0
    })
  })
  
  sortedLogs.forEach(log => {
    const level = detectLogLevel(log.message)
    const bucketIndex = totalDuration > 0 
      ? Math.min(Math.floor((log.timestamp - startTime) / bucketDuration), numBuckets - 1)
      : 0
    
    buckets[bucketIndex].total++
    if (level === 'ERROR') {
      buckets[bucketIndex].error++
      if (buckets[bucketIndex].containerErrors[log.containerId] !== undefined) {
        buckets[bucketIndex].containerErrors[log.containerId]++
      }
    } else if (level === 'WARN') {
      buckets[bucketIndex].warn++
      if (buckets[bucketIndex].containerWarns[log.containerId] !== undefined) {
        buckets[bucketIndex].containerWarns[log.containerId]++
      }
    }
  })
  
  const labels = buckets.map((_, i) => {
    const bucketTime = startTime + (i + 0.5) * bucketDuration
    return formatShortTime(bucketTime)
  })
  
  const errorRates = buckets.map(b => b.total > 0 ? ((b.error + b.warn) / b.total) * 100 : 0)
  
  const containerErrors = {}
  const containerWarns = {}
  
  props.selectedContainers.forEach(id => {
    containerErrors[id] = buckets.map(b => b.containerErrors[id] || 0)
    containerWarns[id] = buckets.map(b => b.containerWarns[id] || 0)
  })
  
  return {
    labels,
    errorRates,
    containerErrors,
    containerWarns
  }
}

function formatShortTime(timestamp) {
  const date = new Date(timestamp * 1000)
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

watch([() => props.logs, () => props.selectedContainers], () => {
  if (isExpanded.value) {
    nextTick(() => {
      initContainerChart()
      initTrendChart()
    })
  }
}, { deep: true })

watch(isExpanded, (newValue) => {
  if (newValue) {
    nextTick(() => {
      initContainerChart()
      initTrendChart()
    })
  }
})

onMounted(() => {
  nextTick(() => {
    if (isExpanded.value) {
      initContainerChart()
      initTrendChart()
    }
  })
})

onUnmounted(() => {
  if (trendChart) {
    trendChart.destroy()
    trendChart = null
  }
  if (containerChart) {
    containerChart.destroy()
    containerChart = null
  }
})
</script>

<style scoped>
.stats-panel {
  margin-bottom: 1.5rem;
  background-color: var(--bg-primary);
  border-radius: 0.5rem;
  overflow: hidden;
  border: 1px solid var(--border-color);
}

.stats-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background-color: var(--bg-secondary);
  cursor: pointer;
  user-select: none;
  transition: background-color 0.2s;
}

.stats-header:hover {
  background-color: rgba(59, 130, 246, 0.1);
}

.stats-title {
  font-weight: 600;
  font-size: 0.9375rem;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.stats-title .icon {
  font-size: 1.1rem;
}

.toggle-icon {
  color: var(--text-secondary);
  font-size: 0.75rem;
  transition: transform 0.3s;
}

.stats-content {
  padding: 1rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
}

.stats-card {
  background-color: var(--bg-secondary);
  border-radius: 0.375rem;
  padding: 1rem;
}

.stats-card-full {
  grid-column: 1 / -1;
}

.stats-card h3 {
  margin: 0 0 0.75rem 0;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-color);
}

/* Container Overview */
.container-overview {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 0.75rem;
}

.container-summary {
  background-color: var(--bg-primary);
  border-radius: 0.375rem;
  padding: 0.75rem;
  border-left: 3px solid var(--primary-color);
}

.container-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.color-badge {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid white;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.container-name {
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--text-primary);
}

.container-stats {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.75rem;
}

.stat-label {
  color: var(--text-secondary);
}

.stat-value {
  font-weight: 600;
  color: var(--text-primary);
}

.stat-value.error {
  color: #ef4444;
}

.stat-value.warn {
  color: #f59e0b;
}

/* Level Distribution */
.level-distribution {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.level-item {
  display: grid;
  grid-template-columns: 60px 50px 1fr;
  align-items: center;
  gap: 0.75rem;
  padding: 0.25rem 0;
}

.level-name {
  font-weight: 600;
  font-size: 0.8125rem;
}

.level-item.level-error .level-name { color: #ef4444; }
.level-item.level-warn .level-name { color: #f59e0b; }
.level-item.level-info .level-name { color: #3b82f6; }
.level-item.level-debug .level-name { color: #10b981; }
.level-item.level-unknown .level-name { color: #6b7280; }

.level-count {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  text-align: right;
}

.level-bar {
  height: 8px;
  background-color: #374151;
  border-radius: 4px;
  overflow: hidden;
}

.level-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

.level-item.level-error .level-bar-fill { background-color: #ef4444; }
.level-item.level-warn .level-bar-fill { background-color: #f59e0b; }
.level-item.level-info .level-bar-fill { background-color: #3b82f6; }
.level-item.level-debug .level-bar-fill { background-color: #10b981; }
.level-item.level-unknown .level-bar-fill { background-color: #6b7280; }

.summary-text {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border-color);
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

.summary-text strong {
  color: var(--text-primary);
}

.error-rate {
  margin-left: 0.5rem;
}

.error-rate strong.high {
  color: #ef4444;
}

.chart-container {
  height: 200px;
  width: 100%;
}

.collapse-enter-active,
.collapse-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.collapse-enter-from,
.collapse-leave-to {
  opacity: 0;
  max-height: 0;
}

.collapse-enter-to,
.collapse-leave-from {
  max-height: 1000px;
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
  
  .level-item {
    grid-template-columns: 50px 40px 1fr;
    gap: 0.5rem;
  }
  
  .container-overview {
    grid-template-columns: 1fr;
  }
}
</style>
