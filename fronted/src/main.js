import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import ContainerList from './views/ContainerList.vue'
import LogViewer from './views/LogViewer.vue'

const routes = [
  {
    path: '/',
    name: 'ContainerList',
    component: ContainerList
  },
  {
    path: '/containers/:id',
    name: 'LogViewer',
    component: LogViewer
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

const app = createApp(App)
app.use(router)
app.mount('#app')
