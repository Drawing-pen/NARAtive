import { createApp } from 'vue'
import { Icon } from '@iconify/vue'

import '@fontsource-variable/fraunces'
import '@fontsource-variable/literata'
import '@fontsource-variable/source-sans-3'
import './style.css'
import './lib/icons'

import App from './App.vue'
import router from './router'

const app = createApp(App)

app.component('Icon', Icon)
app.use(router)

app.mount('#app')