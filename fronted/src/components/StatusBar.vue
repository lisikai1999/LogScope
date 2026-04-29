<template>
  <div class="status-bar">
    <div class="status-bar-content" :class="{ 'center-content': isInputFocused }">
      <div v-if="isInputFocused" class="status-section-centered">
        <span class="status-text">
          ⚠️ 输入框已聚焦，全局快捷键暂时禁用
        </span>
      </div>
      <div v-else class="shortcuts-section">
        <span class="shortcuts-label">快捷键:</span>
        <div class="shortcuts-list">
          <div 
            v-for="(shortcut, index) in currentPageShortcuts" 
            :key="index"
            class="shortcut-item"
          >
            <span class="shortcut-key">{{ shortcut.display }}</span>
            <span class="shortcut-desc">{{ shortcut.description }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { currentPageShortcuts } from '../composables/useKeyboardShortcuts'

const isInputFocused = ref(false)

const checkInputFocus = () => {
  const activeElement = document.activeElement
  const tagName = activeElement?.tagName?.toLowerCase()
  const isEditable = activeElement?.getAttribute('contenteditable') === 'true'
  isInputFocused.value = ['input', 'textarea', 'select'].includes(tagName) || isEditable
}

let focusListener = null
let blurListener = null

onMounted(() => {
  focusListener = () => {
    setTimeout(checkInputFocus, 0)
  }
  blurListener = () => {
    setTimeout(checkInputFocus, 0)
  }
  
  document.addEventListener('focusin', focusListener)
  document.addEventListener('focusout', blurListener)
  
  checkInputFocus()
})

onUnmounted(() => {
  if (focusListener) {
    document.removeEventListener('focusin', focusListener)
  }
  if (blurListener) {
    document.removeEventListener('focusout', blurListener)
  }
})
</script>

<style scoped>
.status-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background-color: var(--bg-primary);
  border-top: 1px solid var(--border-color);
  padding: 0.5rem 1rem;
  z-index: 1000;
  box-shadow: 0 -1px 3px rgba(0, 0, 0, 0.05);
}

.status-bar-content {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.status-bar-content.center-content {
  justify-content: center;
}

.shortcuts-section {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.shortcuts-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.shortcuts-list {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.shortcut-item {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.75rem;
}

.shortcut-key {
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 0.25rem;
  padding: 0.125rem 0.375rem;
  font-family: 'Courier New', monospace;
  font-weight: 600;
  color: var(--primary-color);
}

.shortcut-desc {
  color: var(--text-secondary);
}

.status-section-centered {
  display: flex;
  align-items: center;
  justify-content: center;
}

.status-text {
  font-size: 0.75rem;
  color: var(--warning-color);
  font-weight: 500;
}

@media (max-width: 768px) {
  .status-bar {
    padding: 0.5rem;
  }
  
  .shortcuts-list {
    gap: 0.5rem;
  }
  
  .shortcut-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 0;
  }
}
</style>
