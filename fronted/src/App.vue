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
  --bg-secondary: #f3f4f6;
  --text-primary: #111827;
  --text-secondary: #6b7280;
  --border-color: #e5e7eb;
  --primary-color: #3b82f6;
  --success-color: #10b981;
  --error-color: #ef4444;
  --warning-color: #f59e0b;
}

body {
  background-color: var(--bg-secondary);
  color: var(--text-primary);
  margin: 0;
  padding: 0;
  padding-bottom: 40px;
}

#app {
  min-height: 100vh;
}
</style>
