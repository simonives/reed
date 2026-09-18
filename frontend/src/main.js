import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { ripple } from './directives/ripple'
import './styles/tokens.css'
import './styles/base.css'

createApp(App).use(createPinia()).directive('ripple', ripple).mount('#app')
