<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import { ApiError } from '../api/types'

const router = useRouter()
const auth = useAuthStore()
const message = useMessage()

const email = ref('')
const password = ref('')
const submitting = ref(false)

async function handleSubmit(): Promise<void> {
  // Defensive guard against re-entry. The form/button wiring below should
  // already prevent double-submit, but a stray future change could reintroduce
  // it — and a double-submit here races on the backend's email uniqueness
  // check, surfacing as 500s. Cheap to keep.
  if (submitting.value) return

  if (!email.value || !password.value) {
    message.error('Email and password are required.')
    return
  }
  submitting.value = true
  try {
    await auth.login({ email: email.value, password: password.value })
    await router.push({ name: 'dashboard' })
  } catch (err) {
    if (err instanceof ApiError) {
      message.error(err.message)
    } else {
      message.error('Login failed: unexpected error.')
      throw err
    }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <n-space vertical align="center" :size="24" style="padding: 4rem 1rem;">
    <n-h1 style="margin: 0;">Sign in</n-h1>
    <n-card style="width: min(360px, 92vw);">
      <!--
        ONE submit trigger. The form's submit event fires for both button click
        (because the button is attr-type="submit") and Enter in any input.
        Do NOT also add @click on the button or @keyup.enter on inputs — that
        creates a double-submit that races on the backend.
      -->
      <n-form @submit.prevent="handleSubmit">
        <n-form-item label="Email" path="email">
          <n-input
            v-model:value="email"
            type="text"
            placeholder="alice@example.com"
            :input-props="{ autocomplete: 'username', autocapitalize: 'off' }"
          />
        </n-form-item>
        <n-form-item label="Password" path="password">
          <n-input
            v-model:value="password"
            type="password"
            show-password-on="click"
            :input-props="{ autocomplete: 'current-password' }"
          />
        </n-form-item>
        <n-button
          type="primary"
          block
          attr-type="submit"
          :loading="submitting"
        >
          Sign in
        </n-button>
      </n-form>
      <n-divider style="margin: 1.25rem 0 0.75rem;" />
      <n-space justify="center" :size="6">
        <n-text depth="3">No account?</n-text>
        <RouterLink to="/register">Register</RouterLink>
      </n-space>
    </n-card>
  </n-space>
</template>
