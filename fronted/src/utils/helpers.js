
export function getContainerName(names) {
  if (!names || names.length === 0) return 'N/A'
  return names[0].replace(/^\//, '')
}

export function formatDate(timestamp) {
  if (!timestamp) return 'N/A'
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN')
}

export function formatLogTime(timestamp) {
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

export function formatShortTime(timestamp) {
  const date = new Date(timestamp * 1000)
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

export function formatTimestamp(timestamp) {
  if (!timestamp) return 'N/A'
  const date = new Date(timestamp * 1000)
  return date.toLocaleString('zh-CN')
}

export function formatBytes(bytes) {
  if (bytes === 0 || !bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

export function formatDateTimeLocal(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day}T${hours}:${minutes}`
}

export function getStatusClass(state) {
  const classes = {
    running: 'status-running',
    exited: 'status-stopped',
    paused: 'status-paused'
  }
  return classes[state] || 'status-unknown'
}

export function detectLogLevel(message) {
  if (!message) return 'UNKNOWN'
  
  const upperMessage = message.toUpperCase()
  
  if (upperMessage.includes('ERROR') || 
      upperMessage.includes('FATAL') || 
      upperMessage.includes('CRITICAL') || 
      upperMessage.includes('ERR]') || 
      upperMessage.includes('ERROR:')) {
    return 'ERROR'
  }
  if (upperMessage.includes('WARN') || 
      upperMessage.includes('WARNING') || 
      upperMessage.includes('WARN]')) {
    return 'WARN'
  }
  if (upperMessage.includes('INFO') || 
      upperMessage.includes('INFORMATION') || 
      upperMessage.includes('INFO]')) {
    return 'INFO'
  }
  if (upperMessage.includes('DEBUG') || 
      upperMessage.includes('TRACE') || 
      upperMessage.includes('VERBOSE') || 
      upperMessage.includes('DEBUG]')) {
    return 'DEBUG'
  }
  
  return 'UNKNOWN'
}

export function extractWords(message) {
  if (!message) return []
  const matches = message.match(/[a-zA-Z]{3,}/g)
  return matches || []
}

export function escapeHtml(text) {
  if (!text) return ''
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

export function highlightLogMessage(log) {
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

export function getProgressWidth(percent) {
  const clamped = Math.max(0, Math.min(100, percent))
  return clamped + '%'
}

export default {
  getContainerName,
  formatDate,
  formatLogTime,
  formatShortTime,
  formatTimestamp,
  formatBytes,
  formatDateTimeLocal,
  getStatusClass,
  detectLogLevel,
  extractWords,
  escapeHtml,
  highlightLogMessage,
  getProgressWidth
}
