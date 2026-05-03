<template>
  <div id="app">
    <router-view />
    <StatusBar />
  </div>
</template>

<script>
import StatusBar from './components/StatusBar.vue'

export default {
  name: 'App',
  components: {
    StatusBar
  }
}
</script>

<style>
:root {
  --bg-primary: #ffffff;
  --bg-secondary: #f8fafc;
  --bg-tertiary: #f1f5f9;
  --text-primary: #1e293b;
  --text-secondary: #64748b;
  --text-muted: #94a3b8;
  --border-color: #e2e8f0;
  --border-light: #f1f5f9;
  --primary-color: #3b82f6;
  --primary-hover: #2563eb;
  --primary-light: #dbeafe;
  --success-color: #10b981;
  --success-hover: #059669;
  --success-light: #d1fae5;
  --error-color: #ef4444;
  --error-hover: #dc2626;
  --error-light: #fee2e2;
  --warning-color: #f59e0b;
  --warning-hover: #d97706;
  --warning-light: #fef3c7;
  --info-color: #6366f1;
  --info-hover: #4f46e5;
  --info-light: #e0e7ff;

  --sidebar-bg: #1e293b;
  --sidebar-hover: #334155;
  --sidebar-active-bg: #334155;
  --sidebar-border: #475569;
  --sidebar-text: #e2e8f0;
  --sidebar-secondary: #94a3b8;
  --sidebar-primary: #60a5fa;

  --card-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1);
  --card-shadow-hover: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
}

body {
  background-color: var(--bg-secondary);
  color: var(--text-primary);
  margin: 0;
  padding: 0;
  padding-bottom: 40px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#app {
  min-height: 100vh;
}

* {
  box-sizing: border-box;
}

*::before,
*::after {
  box-sizing: border-box;
}

a {
  color: var(--primary-color);
  text-decoration: none;
  transition: color 0.2s;
}

a:hover {
  color: var(--primary-hover);
}

::selection {
  background-color: var(--primary-light);
  color: var(--text-primary);
}

::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: var(--bg-tertiary);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb {
  background: var(--text-muted);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--text-secondary);
}
</style>
