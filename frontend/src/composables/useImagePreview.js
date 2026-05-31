import { computed, reactive } from 'vue';

export function useImagePreview() {
  const previewState = reactive({
    open: false,
    images: [],
    index: 0,
  });

  const currentPreviewImage = computed(() => {
    return previewState.images[previewState.index] || null;
  });

  function openImagePreview(images, index = 0) {
    previewState.images = Array.isArray(images) ? images.slice() : [];
    previewState.index = Math.max(0, Math.min(index, previewState.images.length - 1));
    previewState.open = previewState.images.length > 0;
  }

  function closeImagePreview() {
    previewState.open = false;
    previewState.images = [];
    previewState.index = 0;
  }

  function shiftPreview(step) {
    if (!previewState.images.length) {
      return;
    }
    const total = previewState.images.length;
    previewState.index = (previewState.index + step + total) % total;
  }

  return {
    closeImagePreview,
    currentPreviewImage,
    openImagePreview,
    previewState,
    shiftPreview,
  };
}
