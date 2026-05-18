<script setup lang="ts">
import { ref } from 'vue'
import { themeOverrides } from './styles/theme'

const clicks = ref(0)
</script>

<template>
  <n-config-provider :theme="null" :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-dialog-provider>
        <main>
          <n-space vertical align="center" :size="16" style="padding: 3rem">
            <n-h1>Trading Journal</n-h1>
            <n-p depth="3">Phase F0.1 scaffold — Vite + Vue 3 + TypeScript + Naive UI.</n-p>
            <n-button type="primary" @click="clicks++">
              Hello, F0.1 — clicks: {{ clicks }}
            </n-button>
          </n-space>
        </main>
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>
