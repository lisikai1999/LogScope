import { ref, onUnmounted, watch } from 'vue'

const shortcuts = ref([])
const currentPageShortcuts = ref([])

const isInputFocused = () => {
  const activeElement = document.activeElement
  const tagName = activeElement?.tagName?.toLowerCase()
  const isEditable = activeElement?.getAttribute('contenteditable') === 'true'
  return ['input', 'textarea', 'select'].includes(tagName) || isEditable
}

const formatShortcutDisplay = (shortcut) => {
  const parts = []
  if (shortcut.ctrl) parts.push('Ctrl')
  if (shortcut.alt) parts.push('Alt')
  if (shortcut.shift) parts.push('Shift')
  if (shortcut.meta) parts.push('Cmd')
  
  let keyDisplay = shortcut.key.toUpperCase()
  if (shortcut.key === 'ArrowUp') keyDisplay = '↑'
  if (shortcut.key === 'ArrowDown') keyDisplay = '↓'
  if (shortcut.key === 'ArrowLeft') keyDisplay = '←'
  if (shortcut.key === 'ArrowRight') keyDisplay = '→'
  if (shortcut.key === 'Escape') keyDisplay = 'Esc'
  if (shortcut.key === ' ') keyDisplay = 'Space'
  if (shortcut.key === 'Enter') keyDisplay = 'Enter'
  
  parts.push(keyDisplay)
  return parts.join('+')
}

const registerShortcut = (shortcut) => {
  const existingIndex = shortcuts.value.findIndex(s => 
    s.key === shortcut.key &&
    s.ctrl === shortcut.ctrl &&
    s.alt === shortcut.alt &&
    s.shift === shortcut.shift &&
    s.meta === shortcut.meta &&
    s.pageId === shortcut.pageId
  )
  
  if (existingIndex !== -1) {
    shortcuts.value[existingIndex] = shortcut
  } else {
    shortcuts.value.push(shortcut)
  }
  
  updateCurrentPageShortcuts()
}

const unregisterShortcut = (pageId, key) => {
  shortcuts.value = shortcuts.value.filter(s => 
    !(s.pageId === pageId && s.key === key)
  )
  updateCurrentPageShortcuts()
}

const unregisterAllByPage = (pageId) => {
  shortcuts.value = shortcuts.value.filter(s => s.pageId !== pageId)
  updateCurrentPageShortcuts()
}

const updateCurrentPageShortcuts = () => {
  const path = window.location.pathname
  let pageId = 'container-list'
  
  if (path.startsWith('/containers/')) {
    pageId = 'log-viewer'
  } else if (path === '/dashboard') {
    pageId = 'dashboard'
  } else if (path === '/multi-logs') {
    pageId = 'multi-logs'
  }
  
  currentPageShortcuts.value = shortcuts.value
    .filter(s => s.pageId === pageId || s.pageId === 'global')
    .map(s => ({
      key: s.key,
      display: formatShortcutDisplay(s),
      description: s.description,
      preventDefault: s.preventDefault !== false
    }))
}

const handleKeydown = (event) => {
  const path = window.location.pathname
  let pageId = 'container-list'
  
  if (path.startsWith('/containers/')) {
    pageId = 'log-viewer'
  } else if (path === '/dashboard') {
    pageId = 'dashboard'
  } else if (path === '/multi-logs') {
    pageId = 'multi-logs'
  }
  
  const matchingShortcuts = shortcuts.value.filter(s => {
    if (s.pageId !== pageId && s.pageId !== 'global') return false
    
    const keyMatch = s.key === event.key || 
                      (s.key === 'ArrowUp' && event.key === 'ArrowUp') ||
                      (s.key === 'ArrowDown' && event.key === 'ArrowDown') ||
                      (s.key === ' ' && event.key === ' ')
    
    return keyMatch &&
           s.ctrl === event.ctrlKey &&
           s.alt === event.altKey &&
           s.shift === event.shiftKey &&
           s.meta === event.metaKey
  })
  
  if (matchingShortcuts.length > 0) {
    const shortcut = matchingShortcuts[0]
    
    if (shortcut.preventDefault !== false) {
      event.preventDefault()
    }
    
    if (isInputFocused() && !shortcut.allowInInput) {
      return
    }
    
    if (shortcut.handler) {
      shortcut.handler(event)
    }
  }
}

const setupGlobalListener = () => {
  window.addEventListener('keydown', handleKeydown)
  
  window.addEventListener('popstate', updateCurrentPageShortcuts)
  
  const originalPushState = window.history.pushState
  window.history.pushState = function(...args) {
    originalPushState.apply(this, args)
    updateCurrentPageShortcuts()
  }
  
  const originalReplaceState = window.history.replaceState
  window.history.replaceState = function(...args) {
    originalReplaceState.apply(this, args)
    updateCurrentPageShortcuts()
  }
}

setupGlobalListener()

export const useKeyboardShortcuts = (pageId) => {
  const register = (config) => {
    const shortcut = {
      ...config,
      pageId,
      ctrl: config.ctrl || false,
      alt: config.alt || false,
      shift: config.shift || false,
      meta: config.meta || false,
      allowInInput: config.allowInInput || false,
      preventDefault: config.preventDefault !== false
    }
    registerShortcut(shortcut)
  }
  
  const unregister = (key) => {
    unregisterShortcut(pageId, key)
  }
  
  const clearAll = () => {
    unregisterAllByPage(pageId)
  }
  
  onUnmounted(() => {
    clearAll()
  })
  
  return {
    register,
    unregister,
    clearAll,
    currentPageShortcuts,
    isInputFocused
  }
}

export { currentPageShortcuts }
