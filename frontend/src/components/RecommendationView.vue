<script setup>
import { onBeforeUnmount, ref, watch } from "vue";
import { api } from "../api.js";
import { PLACE_CATEGORIES } from "../categories.js";

const props = defineProps({
  item: { type: Object, required: true },
  lists: { type: Array, required: true },
  editOnOpen: { type: Boolean, default: false },
});
const emit = defineEmits(["back", "liked", "seen", "to-list", "deleted", "open-author"]);

const current = ref(props.item);
const error = ref("");
const photoUrls = ref([]);
const editing = ref(false);
const busy = ref(false);
const friends = ref([]);
const name = ref("");
const text = ref("");
const visibility = ref("friends");
const category = ref("");
const audience = ref([]);

function revokePhotos() {
  for (const url of photoUrls.value) URL.revokeObjectURL(url);
  photoUrls.value = [];
}

async function loadPhotos(item) {
  revokePhotos();
  const urls = [];
  for (const photo of item.photos ?? []) {
    const blob = await api.recommendationPhotoBlob(item.id, photo.id);
    urls.push(URL.createObjectURL(blob));
  }
  photoUrls.value = urls;
}

watch(
  () => [current.value.id, ...(current.value.photos ?? []).map((photo) => photo.id)].join(","),
  () => {
    loadPhotos(current.value).catch((err) => {
      error.value = err.message;
    });
  },
  { immediate: true },
);

onBeforeUnmount(revokePhotos);

async function openPage(item) {
  current.value = item;
  error.value = "";
  try {
    current.value = await api.recommendation(item.id);
    emit("seen", item.id);
    if (props.editOnOpen && current.value.is_own) await startEdit();
  } catch (err) {
    error.value = err.message;
  }
}

watch(
  () => [props.item.id, props.editOnOpen],
  ([id, editing], previous) => {
    const openedAnother = !previous || previous[0] !== id;
    const askedToEdit = Boolean(editing) && (!previous || !previous[1]);
    if (openedAnother || askedToEdit) openPage(props.item);
  },
  { immediate: true },
);

async function publish() {
  error.value = "";
  try {
    current.value = await api.publishRecommendation(current.value.id);
    emit("liked", current.value);
  } catch (err) {
    error.value = err.message;
  }
}

async function like() {
  error.value = "";
  try {
    current.value = await api.toggleLike(current.value.id);
    emit("liked", current.value);
  } catch (err) {
    error.value = err.message;
  }
}

async function addPhoto(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  error.value = "";
  try {
    current.value = await api.uploadRecommendationPhoto(current.value.id, file);
    emit("liked", current.value);
  } catch (err) {
    error.value = err.message;
  }
}

async function startEdit() {
  error.value = "";
  name.value = current.value.place.name;
  text.value = current.value.text;
  visibility.value = current.value.visibility;
  category.value = current.value.category || "";
  audience.value = [...(current.value.audience ?? [])];
  editing.value = true;
  try {
    friends.value = await api.friends();
  } catch (err) {
    error.value = err.message;
  }
}

async function saveEdit() {
  error.value = "";
  busy.value = true;
  try {
    current.value = await api.updateRecommendation(current.value.id, {
      name: name.value.trim(),
      text: text.value.trim(),
      visibility: visibility.value,
      category: category.value,
      audience: visibility.value === "allow" || visibility.value === "deny" ? audience.value : [],
    });
    editing.value = false;
    emit("liked", current.value);
  } catch (err) {
    error.value = err.message;
  } finally {
    busy.value = false;
  }
}

async function remove() {
  if (!window.confirm("Удалить рекомендацию? В списках других людей останется только место.")) return;
  error.value = "";
  busy.value = true;
  try {
    await api.deleteRecommendation(current.value.id);
    emit("deleted", current.value.id);
  } catch (err) {
    error.value = err.message;
    busy.value = false;
  }
}

</script>

<template>
  <section class="page">
    <button class="link" @click="emit('back')">Назад</button>
    <form v-if="editing" class="stack" @submit.prevent="saveEdit">
      <label>Название <input v-model="name" maxlength="200" required /></label>
      <label>Рекомендация <textarea v-model="text" rows="4" maxlength="2000" required /></label>
      <label>
        Категория
        <select v-model="category">
          <option value="">Без категории</option>
          <option v-for="item in PLACE_CATEGORIES" :key="item.id" :value="item.id">{{ item.label }}</option>
        </select>
      </label>
      <label>
        Кто видит
        <select v-model="visibility">
          <option value="friends">Друзья</option>
          <option value="close">Близкие друзья</option>
          <option value="allow">Только выбранные друзья</option>
          <option value="deny">Все друзья, кроме выбранных</option>
          <option value="everyone">Все</option>
          <option value="self">Только я</option>
        </select>
      </label>
      <fieldset v-if="visibility === 'allow' || visibility === 'deny'">
        <legend>Друзья</legend>
        <label v-for="friend in friends" :key="friend.id">
          <input v-model="audience" type="checkbox" :value="friend.username" />
          {{ friend.display_name }} @{{ friend.username }}
        </label>
      </fieldset>
      <button class="primary" :disabled="busy">Сохранить</button>
      <button type="button" class="link" @click="editing = false">Отмена</button>
    </form>
    <template v-else>
      <h2>{{ current.place.name }}</h2>
      <p v-if="current.place.address" class="muted">{{ current.place.address }}</p>
      <p v-if="current.text">{{ current.text }}</p>
    </template>
    <div v-if="photoUrls.length" class="photo-row">
      <img v-for="url in photoUrls" :key="url" :src="url" alt="Фото места" />
    </div>
    <label v-if="current.is_own && (current.photos?.length ?? 0) < 5">
      Фото
      <input type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" @change="addPhoto" />
    </label>
    <p>
      <button class="link" @click="emit('open-author', current.author.public_id)">{{ current.author.display_name }}</button>
      <span class="muted"> @{{ current.author.username }}</span>
    </p>
    <div class="actions">
      <button v-if="current.is_own && !editing" @click="startEdit">Изменить</button>
      <button v-if="current.is_own && !editing" class="danger" :disabled="busy" @click="remove">Удалить</button>
      <button v-if="current.is_own && !editing && current.status === 'draft'" class="primary" @click="publish">Опубликовать</button>
      <button v-if="current.on_map" @click="like">{{ current.liked ? "Убрать лайк" : "Лайк" }} · {{ current.like_count }}</button>
      <button v-if="current.on_map" @click="emit('to-list', current.place)">В избранное</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>
