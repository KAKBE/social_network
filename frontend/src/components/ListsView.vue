<script setup>
import { ref } from "vue";

defineProps({ lists: { type: Array, required: true } });
const emit = defineEmits(["create", "remove", "show-on-map"]);
const title = ref("");

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
    <form class="search" @submit.prevent="create">
      <input v-model="title" maxlength="100" placeholder="Новый список, например «Свидания»" />
      <button>Создать</button>
    </form>
    <article v-for="l in lists" :key="l.id" class="card">
      <h3>{{ l.title }} <span class="muted">· {{ l.places.length }}</span></h3>
      <p v-if="!l.places.length" class="muted">Пока пусто. Сохраните место из ленты или с карты.</p>
      <ul class="list-places">
        <li v-for="p in l.places" :key="p.id">
          <button class="link" @click="emit('show-on-map', p)">{{ p.name }}</button>
          <button class="icon" aria-label="Убрать из списка" @click="emit('remove', l.id, p.id)">✕</button>
        </li>
      </ul>
    </article>
  </section>
</template>
