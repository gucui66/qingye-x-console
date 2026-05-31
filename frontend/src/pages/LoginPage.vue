<template>
  <div class="login-page">
    <div class="login-hero">
      <div class="login-kicker">{{ t('login.kicker') }}</div>
      <h1>{{ t('login.title') }}</h1>
      <p>
        {{ t('login.description') }}
      </p>
      <ul class="login-feature-list">
        <li>{{ t('login.feature.navigation') }}</li>
        <li>{{ t('login.feature.tasks') }}</li>
        <li>{{ t('login.feature.database') }}</li>
        <li>{{ t('login.feature.deployment') }}</li>
      </ul>
    </div>

    <a-card class="login-card" :bordered="false">
      <template #title>{{ t('login.cardTitle') }}</template>
      <a-form :model="form" layout="vertical" @finish="handleSubmit">
        <a-form-item :label="t('login.username')" name="username">
          <a-input v-model:value="form.username" :placeholder="t('login.usernamePlaceholder')" />
        </a-form-item>
        <a-form-item :label="t('login.password')" name="password">
          <a-input-password v-model:value="form.password" :placeholder="t('login.passwordPlaceholder')" @pressEnter="handleSubmit" />
        </a-form-item>
        <a-alert
          v-if="errorMessage"
          type="error"
          show-icon
          :message="errorMessage"
          class="login-alert"
        />
        <a-space direction="vertical" style="width: 100%">
          <a-button type="primary" html-type="button" block :loading="submitting" @click="handleSubmit">
            {{ t('login.submit') }}
          </a-button>
          <div class="login-hint">{{ t('login.hint') }}</div>
        </a-space>
      </a-form>
    </a-card>
  </div>
</template>

<script setup>
import { reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { t } from '../lib/i18n';
import { useWorkbenchStore } from '../store/workbench';

const router = useRouter();
const route = useRoute();
const store = useWorkbenchStore();

const form = reactive({
  username: 'admin',
  password: '',
});

const submitting = ref(false);
const errorMessage = ref('');

function resolveRedirect() {
  return typeof route.query.redirect === 'string' && route.query.redirect.startsWith('/')
    ? route.query.redirect
    : '/dashboard';
}

watch(
  () => store.state.auth.loggedIn,
  (loggedIn) => {
    if (loggedIn) {
      router.replace(resolveRedirect());
    }
  },
  { immediate: true }
);

async function handleSubmit() {
  if (submitting.value) {
    return;
  }

  if (!String(form.username || '').trim() || !String(form.password || '').trim()) {
    errorMessage.value = t('login.required');
    return;
  }

  submitting.value = true;
  errorMessage.value = '';

  try {
    await store.login({
      username: String(form.username || '').trim(),
      password: String(form.password || '').trim(),
    });
    router.replace(resolveRedirect());
  } catch (error) {
    errorMessage.value = error.message || t('login.failed');
  } finally {
    submitting.value = false;
  }
}
</script>
