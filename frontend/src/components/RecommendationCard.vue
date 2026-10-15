<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  item: { type: Object, required: true },
  lists: { type: Array, required: true },
  showMapButton: { type: Boolean, default: false },
  closable: { type: Boolean, default: false },
});
const emit = defineEmits(["save", "show-on-map", "close"]);

const listId = ref(props.lists[0]?.id ?? null);
const savedIn = computed(() =>
  props.lists.filter((l) => l.places.some((p) => p.id === props.item.place.id)).map((l) => l.title),
);
const date = computed(() => new Date(props.item.created_at).toLocaleDateString("ru-RU"));
</script>

<template>
  <article class="card">
    <header class="card-head">
      <div>
        <h3>{{ item.place.name }}</h3>
        <p class="muted">
          {{ item.is_own ? "Ваша рекомендация" : `Рекомендует ${item.author.display_name}` }} · {{ date }}
        </p>
      </div>
      <button v-if="closable" class="icon" aria-label="Закрыть" @click="emit('close')">✕</button>
    </header>
    <p class="card-text">{{ item.text }}</p>
    <p v-if="savedIn.length" class="saved">Сохранено: {{ savedIn.join(", ") }}</p>
    <div class="card-actions">
      <button v-if="showMapButton" class="secondary" @click="emit('show-on-map', item)">На карте</button>
      <template v-if="lists.length">
        <select v-model="listId" aria-label="Список">
          <option v-for="l in lists" :key="l.id" :value="l.id">{{ l.title }}</option>
        </select>
        <button @click="emit('save', listId, item.place.id)">Сохранить</button>
      </template>
    </div>
  </article>
</template>
