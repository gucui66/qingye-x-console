<template>
  <a-space direction="vertical" size="large" style="width: 100%">
    <a-card :title="t('settings.language.title')" class="panel-card">
      <a-space direction="vertical" style="width: 100%">
        <a-alert
          type="info"
          show-icon
          :message="t('settings.language.description')"
        />
        <a-form layout="vertical">
          <a-form-item :label="t('settings.language.label')">
            <a-select
              :value="currentLanguage"
              :options="languageOptions"
              style="max-width: 260px"
              @change="setLanguage"
            />
          </a-form-item>
        </a-form>
      </a-space>
    </a-card>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :xl="12">
        <a-card :title="t('settings.config.title')" class="panel-card" :loading="store.state.loading.config">
        <a-form layout="vertical" @finish="saveToken">
          <a-form-item label="Twitter Bearer Token">
            <a-input-password
              v-model:value="configForm.bearer_token"
              :placeholder="t('settings.token.placeholder')"
            />
            <div class="setting-help">
              {{ t('settings.token.status') }}
              <a-tag :color="store.state.config?.bearer_token_configured ? 'green' : 'default'">
                {{ store.state.config?.bearer_token_configured ? t('common.configured') : t('common.notConfigured') }}
              </a-tag>
              <span v-if="store.state.config?.bearer_token_masked">
                {{ store.state.config.bearer_token_masked }}
              </span>
            </div>
          </a-form-item>
          <a-space wrap>
            <a-button type="primary" html-type="submit" :loading="savingConfig">
              {{ t('common.save') }}
            </a-button>
            <a-popconfirm
              :title="t('settings.token.clearTitle')"
              :ok-text="t('common.clear')"
              :cancel-text="t('common.cancel')"
              @confirm="clearToken"
            >
              <a-button danger :loading="savingConfig" :disabled="!store.state.config?.bearer_token_configured">
                {{ t('settings.token.clear') }}
              </a-button>
            </a-popconfirm>
          </a-space>
        </a-form>

        <a-divider />

        <a-descriptions :column="1" size="small" bordered>
          <a-descriptions-item :label="t('settings.envFile')">
            <span class="value-wrap break-all" :title="store.state.config?.env_file || '-'">
              {{ store.state.config?.env_file || '-' }}
            </span>
          </a-descriptions-item>
          <a-descriptions-item :label="t('settings.shardsDir')">
            <span class="value-wrap break-all" :title="store.state.config?.media_shards_dir || '-'">
              {{ store.state.config?.media_shards_dir || '-' }}
            </span>
          </a-descriptions-item>
          <a-descriptions-item :label="t('settings.outputDir')">
            <span class="value-wrap break-all" :title="store.state.config?.output_dir || '-'">
              {{ store.state.config?.output_dir || '-' }}
            </span>
          </a-descriptions-item>
          <a-descriptions-item :label="t('settings.port')">
            {{ store.state.config?.port || '5001' }}
          </a-descriptions-item>
        </a-descriptions>
        </a-card>
      </a-col>

      <a-col :xs="24" :xl="12">
        <a-card :title="t('settings.runtime.title')" class="panel-card">
        <a-descriptions :column="1" size="small" bordered style="margin-bottom: 16px">
          <a-descriptions-item :label="t('settings.seleniumHeadless')">
            {{ store.state.config?.selenium_headless ? t('settings.on') : t('settings.off') }}
          </a-descriptions-item>
          <a-descriptions-item :label="t('settings.htmlDoc')">
            {{ store.state.config?.generate_html_doc ? t('settings.on') : t('settings.off') }}
          </a-descriptions-item>
          <a-descriptions-item :label="t('settings.mdDoc')">
            {{ store.state.config?.generate_md_doc ? t('settings.on') : t('settings.off') }}
          </a-descriptions-item>
          <a-descriptions-item :label="t('settings.dataDir')">
            <span class="value-wrap break-all" :title="store.state.config?.data_dir || '-'">
              {{ store.state.config?.data_dir || '-' }}
            </span>
          </a-descriptions-item>
          <a-descriptions-item :label="t('settings.screenshotsDir')">
            <span class="value-wrap break-all" :title="store.state.config?.screenshots_dir || '-'">
              {{ store.state.config?.screenshots_dir || '-' }}
            </span>
          </a-descriptions-item>
        </a-descriptions>
        <a-alert
          type="info"
          show-icon
          :message="t('settings.runtimeNote')"
        />
        </a-card>

        <a-card :title="t('settings.password.title')" class="panel-card" style="margin-top: 16px">
        <a-form layout="vertical" @finish="updatePassword">
          <a-form-item :label="t('settings.password.old')">
            <a-input-password v-model:value="passwordForm.old_password" />
          </a-form-item>
          <a-form-item :label="t('settings.password.new')">
            <a-input-password v-model:value="passwordForm.new_password" />
          </a-form-item>
          <a-form-item :label="t('settings.password.confirm')">
            <a-input-password v-model:value="passwordForm.confirm_password" />
          </a-form-item>
          <a-button type="primary" html-type="submit" :loading="savingPassword">
            {{ t('settings.password.submit') }}
          </a-button>
        </a-form>
        </a-card>

        <a-card :title="t('settings.stack.title')" class="panel-card" style="margin-top: 16px">
        <a-list bordered>
          <a-list-item v-for="item in stackItems" :key="item">{{ item }}</a-list-item>
        </a-list>
        </a-card>

        <a-card :title="t('settings.standalone.title')" class="panel-card" style="margin-top: 16px">
        <a-space direction="vertical" style="width: 100%">
          <a-alert
            type="success"
            show-icon
            :message="t('settings.standalone.message')"
            :description="t('settings.standalone.description')"
          />
          <a-button type="primary" block @click="openStandaloneUserFeed">
            {{ t('settings.standalone.open') }}
          </a-button>
        </a-space>
        </a-card>
      </a-col>
    </a-row>
  </a-space>
</template>

<script setup>
import { message } from 'ant-design-vue';
import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { currentLanguage, languageOptions, setLanguage, t } from '../lib/i18n';
import { useWorkbenchStore } from '../store/workbench';

const store = useWorkbenchStore();
const router = useRouter();

const configForm = reactive({
  bearer_token: '',
});

const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
});

const savingConfig = ref(false);
const savingPassword = ref(false);
const stackItemKeys = [
  'settings.stack.frontend',
  'settings.stack.backend',
  'settings.stack.storage',
  'settings.stack.library',
  'settings.stack.database',
  'settings.stack.deployment',
];
const stackItems = computed(() => stackItemKeys.map((key) => t(key)));

onMounted(async () => {
  const payload = await store.loadConfig();
  configForm.bearer_token = payload?.bearer_token || '';
});

async function saveToken() {
  savingConfig.value = true;
  try {
    const nextToken = configForm.bearer_token.trim();
    await store.saveConfig(nextToken ? { bearer_token: nextToken } : {});
    configForm.bearer_token = '';
    message.success(t('settings.saved'));
  } catch (error) {
    message.error(error.message || t('settings.saveFailed'));
  } finally {
    savingConfig.value = false;
  }
}

async function clearToken() {
  savingConfig.value = true;
  try {
    await store.saveConfig({ clear_bearer_token: true });
    configForm.bearer_token = '';
    message.success(t('settings.tokenCleared'));
  } catch (error) {
    message.error(error.message || t('settings.clearFailed'));
  } finally {
    savingConfig.value = false;
  }
}

async function updatePassword() {
  savingPassword.value = true;
  try {
    await store.changePassword({ ...passwordForm });
    message.success(t('settings.passwordSuccess'));
    passwordForm.old_password = '';
    passwordForm.new_password = '';
    passwordForm.confirm_password = '';
  } catch (error) {
    message.error(error.message || t('settings.passwordFailed'));
  } finally {
    savingPassword.value = false;
  }
}

function openStandaloneUserFeed() {
  const href = router.resolve({
    name: 'user-feed-standalone',
  }).href;
  window.open(href, '_blank', 'noopener,noreferrer');
}
</script>

<style scoped>
.setting-help {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
  color: #53605a;
  font-size: 13px;
}
</style>
