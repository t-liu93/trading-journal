<script setup lang="ts">
import { themeOverrides } from './styles/theme'
</script>

<template>
  <n-config-provider :theme="null" :theme-overrides="themeOverrides">
    <!-- Provider stack so descendant components can call useMessage(), useDialog(). -->
    <n-message-provider>
      <n-dialog-provider>
        <router-view />
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>
