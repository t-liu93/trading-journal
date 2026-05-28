<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const isLegacy = computed(() => route.query.legacy === 'true')
</script>

<template>
  <div>
    <n-text depth="3" style="font-size: 0.85rem;">
      This position will be created with its first Trade — required by the Trade-led model.
    </n-text>
    <n-alert v-if="!isLegacy" type="warning" style="margin-top: 0.75rem;">
      Position creation requires a first Trade. This will be wired in F4. Use <code>?legacy=true</code> for development testing.
    </n-alert>
    <n-alert v-else type="info" style="margin-top: 0.75rem;">
      Legacy mode: creating Position without first Trade. Attach trades via Trades tab or API.
    </n-alert>
  </div>
</template>
