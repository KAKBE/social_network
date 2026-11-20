<script setup>
import { ref, watch } from "vue";

const props = defineProps({
  lists: { type: Array, required: true },
  pending: { type: Object, default: null },
});
const emit = defineEmits(["create", "remove", "show-on-map", "add"]);
const title = ref("");
const selectedId = ref(null);

watch(
  () => props.pending?.id ?? null,
  () => {
    selectedId.value = null;
  },
);

function create() {
  const value = title.value.trim();
  if (!value) return;
  emit("create", value);
  title.value = "";
}
</script>

<template>
  <section class="page">
    <h2>Мои списки</h2>
    <p v-if="pending" class="muted">
      <span v-if="selectedId">✓ </span>{{ pending.name }}
    </p>
    <p v-if="pending && !lists.length" class="muted">Списков нет. Создайте список, выберите его и нажмите «Добавить».</p>
    <form class="search" @submit.prevent="create">
      <input v-model="title" maxlength="100" placeholder="Новый список, например «Свидания»" />
      <button :class="{ primary: !pending }">Создать</button>
    </form>
    <button v-if="pending && selectedId" class="primary" @click="emit('add', selectedId)">Добавить</button>
    <article v-for="l in lists" :key="l.id" class="card">
      <h3>
        <button v-if="pending" class="link" type="button" @click="selectedId = l.id">
          {{ selectedId === l.id ? "✓ " : "" }}{{ l.title }}
        </button>
        <template v-else>{{ l.title }}</template>
        <span class="muted">· {{ l.places.length }}</span>
      </h3>
      <p v-if="!l.places.length" class="muted">Пока пусто. Сохраните место из ленты или с карты.</p>
      <ul class="list-places">
        <li v-for="p in l.places" :key="p.item_id">
          <button class="link" @click="emit('show-on-map', p)">{{ p.name }}</button>
          <p v-if="p.limited" class="muted">{{ p.address }} · {{ p.lat.toFixed(5) }}, {{ p.lon.toFixed(5) }}</p>
          <button class="icon" aria-label="Убрать из списка" @click="emit('remove', l.id, p.item_id)">✕</button>
        </li>
      </ul>
    </article>
  </section>
</template>
