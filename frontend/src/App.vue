<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { themeOverrides } from './styles/theme'
import { useThemeStore } from './stores/theme'

// `naiveTheme` is null (light) or Naive's darkTheme; the store persists the
// choice and seeds it from the OS preference on first visit.
const { naiveTheme } = storeToRefs(useThemeStore())
</script>

<template>
  <n-config-provider :theme="naiveTheme" :theme-overrides="themeOverrides">
    <!-- Paints the <body> background/text to match the active theme; without it
         the area outside n-layout (e.g. the login screen) stays light in dark mode. -->
    <n-global-style />
    <!-- Provider stack so descendant components can call useMessage(), useDialog(). -->
    <n-message-provider>
      <n-dialog-provider>
        <router-view />
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>
