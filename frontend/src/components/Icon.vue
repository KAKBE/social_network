<script setup>
defineProps({
  name: { type: String, required: true },
});
</script>

<template>
  <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
    <path
      v-if="name === 'pin'"
      d="M12 21s7-6.1 7-11a7 7 0 1 0-14 0c0 4.9 7 11 7 11z"
      fill="none"
      stroke="currentColor"
      stroke-width="1.8"
    />
    <circle v-if="name === 'pin'" cx="12" cy="10" r="2.1" fill="currentColor" />
    <path
      v-else-if="name === 'bookmark'"
      d="M7 3.8h10a1 1 0 0 1 1 1V20l-6-3.4L6 20V4.8a1 1 0 0 1 1-1z"
      fill="none"
      stroke="currentColor"
      stroke-width="1.8"
      stroke-linejoin="round"
    />
    <path
      v-else-if="name === 'bookmark-filled'"
      d="M7 3.8h10a1 1 0 0 1 1 1V20l-6-3.4L6 20V4.8a1 1 0 0 1 1-1z"
      fill="currentColor"
    />
    <g v-else-if="name === 'more'" fill="currentColor">
      <circle cx="12" cy="5" r="1.6" />
      <circle cx="12" cy="12" r="1.6" />
      <circle cx="12" cy="19" r="1.6" />
    </g>
    <path
      v-else-if="name === 'pencil'"
      d="M4 16.5V20h3.5L19 8.5 15.5 5 4 16.5z"
      fill="none"
      stroke="currentColor"
      stroke-width="1.8"
      stroke-linejoin="round"
    />
    <path
      v-else-if="name === 'x'"
      d="M7 7l10 10M17 7L7 17"
      fill="none"
      stroke="currentColor"
      stroke-width="1.8"
      stroke-linecap="round"
    />
    <path
      v-else-if="name === 'heart'"
      d="M12 19.2s-6.2-3.8-6.2-8.1a3.5 3.5 0 0 1 6.2-2.2 3.5 3.5 0 0 1 6.2 2.2c0 4.3-6.2 8.1-6.2 8.1z"
      fill="none"
      stroke="currentColor"
      stroke-width="1.8"
      stroke-linejoin="round"
    />
    <path
      v-else-if="name === 'heart-filled'"
      d="M12 19.2s-6.2-3.8-6.2-8.1a3.5 3.5 0 0 1 6.2-2.2 3.5 3.5 0 0 1 6.2 2.2c0 4.3-6.2 8.1-6.2 8.1z"
      fill="currentColor"
    />
    <g v-else-if="name === 'image'">
      <rect x="4" y="5" width="16" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="1.8" />
      <circle cx="9" cy="10" r="1.4" fill="currentColor" />
      <path d="M4 15.5l4.2-3.2 3 2.2 2.4-1.8L20 16.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" />
    </g>
    <path
      v-else-if="name === 'trash'"
      d="M5 7h14M9 7V5h6v2M8 7l.7 12h6.6L16 7"
      fill="none"
      stroke="currentColor"
      stroke-width="1.8"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </svg>
</template>
