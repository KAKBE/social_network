<script setup>
import { ref, watch } from "vue";

const props = defineProps({
  lists: { type: Array, required: true },
  pending: { type: Object, default: null },
});
const emit = defineEmits(["create", "rename", "delete", "remove", "show-on-map", "add"]);
const title = ref("");
const selectedId = ref(null);
const editingId = ref(null);
const draftTitle = ref("");

watch(
  () => props.pending?.id ?? null,
  () => {
    selectedId.value = null;
  },
);

watch(
  () => props.lists,
  (rows) => {
    if (selectedId.value != null && !rows.some((row) => row.id === selectedId.value)) {
      selectedId.value = null;
    }
    if (editingId.value == null) return;
    const current = rows.find((row) => row.id === editingId.value);
    if (current == null || current.title === draftTitle.value.trim()) editingId.value = null;
  },
);

function create() {
  const value = title.value.trim();
  if (!value) return;
  emit("create", value);
  title.value = "";
}

function startRename(list) {
  editingId.value = list.id;
  draftTitle.value = list.title;
}

function saveRename(list) {
  const value = draftTitle.value.trim();
  if (!value || value === list.title) {
    editingId.value = null;
    return;
  }
  emit("rename", list.id, value);
}

function removeList(list) {
  if (!window.confirm(`Удалить «${list.title}»? Места из избранного пропадут.`)) return;
  emit("delete", list.id);
}
</script>

<template>
  <section class="page">
    <h2>Избранное</h2>
    <p v-if="pending" class="muted">
      <span v-if="selectedId">✓ </span>{{ pending.name }}
    </p>
    <p v-if="pending && !lists.length" class="muted">Избранного нет. Создайте подборку, выберите её и нажмите «Добавить».</p>
    <form class="search" @submit.prevent="create">
      <input v-model="title" maxlength="100" placeholder="Новая подборка, например «Свидания»" />
      <button :class="{ primary: !pending }">Создать</button>
    </form>
    <button v-if="pending && selectedId" class="primary" @click="emit('add', selectedId)">Добавить</button>
    <article v-for="l in lists" :key="l.id" class="card">
      <div class="list-head">
        <h3 v-if="editingId !== l.id">
          <button v-if="pending" class="link" type="button" @click="selectedId = l.id">
            {{ selectedId === l.id ? "✓ " : "" }}{{ l.title }}
          </button>
          <template v-else>{{ l.title }}</template>
          <span class="muted">· {{ l.places.length }}</span>
        </h3>
        <form v-else class="search" @submit.prevent="saveRename(l)">
          <input v-model="draftTitle" maxlength="100" :aria-label="`Название «${l.title}»`" />
          <button type="submit">Сохранить</button>
          <button type="button" class="link" @click="editingId = null">Отмена</button>
        </form>
        <div v-if="editingId !== l.id" class="actions">
          <button type="button" @click="startRename(l)">Переименовать</button>
          <button type="button" class="danger" @click="removeList(l)">Удалить</button>
        </div>
      </div>
      <p v-if="!l.places.length" class="muted">Пока пусто. Сохраните место из ленты или с карты.</p>
      <ul class="list-places">
        <li v-for="p in l.places" :key="p.item_id">
          <div>
            <button class="link" @click="emit('show-on-map', p)">{{ p.name }}</button>
            <p v-if="p.limited" class="muted">Рекомендация больше не открывается. Место осталось в избранном.</p>
            <p v-if="p.limited && p.address" class="muted">{{ p.address }}</p>
          </div>
          <button class="icon" aria-label="Убрать из избранного" @click="emit('remove', l.id, p.item_id)">✕</button>
        </li>
      </ul>
    </article>
  </section>
</template>
