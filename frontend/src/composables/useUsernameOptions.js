import { computed } from 'vue';

export function useUsernameOptions(store) {
  const usernameSelectOptions = computed(() => {
    return (store.usernameDirectoryItems.value || [])
      .filter((item) => !item.hidden)
      .map((item) => ({
        label: item.alias ? `${item.display_name} · @${item.username}` : `@${item.username}`,
        value: item.username,
      }));
  });

  function filterUsernameOption(input, option) {
    const keyword = String(input || '').trim().toLowerCase();
    const label = String(option?.label || '').toLowerCase();
    const value = String(option?.value || '').toLowerCase();
    return label.includes(keyword) || value.includes(keyword);
  }

  return {
    filterUsernameOption,
    usernameSelectOptions,
  };
}
