<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { api } from "../api.js";
import { categoryChoices } from "../categories.js";
import Icon from "./Icon.vue";

const props = defineProps({
  item: { type: Object, required: true },
  lists: { type: Array, required: true },
  editOnOpen: { type: Boolean, default: false },
});
const emit = defineEmits(["back", "liked", "to-list", "deleted", "open-author"]);

const current = ref(props.item);
const error = ref("");
const photos = ref([]);
const editing = ref(false);
const busy = ref(false);
const friends = ref([]);
const name = ref("");
const text = ref("");
const visibility = ref("friends");
const category = ref("");
const extraCategories = ref([]);
const choices = computed(() => categoryChoices(extraCategories.value));
const audience = ref([]);

let photoGeneration = 0;

function revokePhotos() {
  for (const photo of photos.value) URL.revokeObjectURL(photo.url);
  photos.value = [];
}

function releasePending(pending) {
  for (const photo of pending) URL.revokeObjectURL(photo.url);
}

async function loadPhotos(item) {
  const generation = ++photoGeneration;
  const next = [];
  try {
    for (const photo of item.photos ?? []) {
      const blob = await api.recommendationPhotoBlob(item.id, photo.id);
      if (generation !== photoGeneration) {
        releasePending(next);
        return;
      }
      next.push({ id: photo.id, url: URL.createObjectURL(blob) });
    }
  } catch (err) {
    releasePending(next);
    throw err;
  }
  if (generation !== photoGeneration) {
    releasePending(next);
    return;
  }
  revokePhotos();
  photos.value = next;
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

async function replacePhoto(photoId, event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  error.value = "";
  try {
    current.value = await api.replaceRecommendationPhoto(current.value.id, photoId, file);
    emit("liked", current.value);
    await loadPhotos(current.value);
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
    const [people, categories] = await Promise.all([api.friends(), api.myCategories()]);
    friends.value = people;
    extraCategories.value = categories;
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
  <section class="page post-page">
    <div class="post-top">
      <button class="link" type="button" @click="emit('back')">Назад</button>
      <div v-if="!editing" class="card-tools">
        <button v-if="current.is_own" class="icon" type="button" aria-label="Изменить" @click="startEdit">
          <Icon name="pencil" />
        </button>
        <button
          v-if="current.on_map"
          class="icon like"
          :class="{ liked: current.liked }"
          type="button"
          :aria-label="current.liked ? 'Убрать лайк' : 'Лайк'"
          :aria-pressed="current.liked"
          @click="like"
        >
          <Icon :name="current.liked ? 'heart-filled' : 'heart'" />
          <span>{{ current.like_count }}</span>
        </button>
        <button
          v-if="current.on_map"
          class="icon saved-action"
          type="button"
          aria-label="В избранное"
          @click="emit('to-list', current.place)"
        >
          <Icon name="bookmark" />
        </button>
      </div>
    </div>
    <form v-if="editing" class="stack edit-sheet" @submit.prevent="saveEdit">
      <h2>Изменение</h2>
      <label>Название <input v-model="name" maxlength="200" required /></label>
      <label>Рекомендация <textarea v-model="text" rows="4" maxlength="2000" required /></label>
      <label>
        Категория
        <select v-model="category">
          <option value="">Без категории</option>
          <option v-for="item in choices" :key="item.id" :value="item.id">{{ item.label }}</option>
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
      <div v-if="photos.length" class="photo-row">
        <figure v-for="photo in photos" :key="photo.id" class="photo-frame">
          <img :src="photo.url" alt="Фото места" />
          <label class="photo-replace">
            Заменить
            <input class="file-hidden" type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" @change="replacePhoto(photo.id, $event)" />
          </label>
        </figure>
      </div>
      <label v-if="(current.photos?.length ?? 0) < 5" class="photo-add">
        <Icon name="image" />
        Добавить фото
        <input class="file-hidden" type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" @change="addPhoto" />
      </label>
      <div class="actions">
        <button class="primary" :disabled="busy">Сохранить</button>
        <button v-if="current.status === 'draft'" type="button" :disabled="busy" @click="publish">Опубликовать</button>
        <button type="button" class="link" @click="editing = false">Отмена</button>
      </div>
      <button type="button" class="danger" :disabled="busy" @click="remove">Удалить рекомендацию</button>
    </form>
    <template v-else>
      <h2>{{ current.place.name }}</h2>
      <p v-if="current.place.address" class="muted">{{ current.place.address }}</p>
      <p v-if="current.text">{{ current.text }}</p>
      <div v-if="photos.length" class="photo-row">
        <img v-for="photo in photos" :key="photo.id" :src="photo.url" alt="Фото места" />
      </div>
      <p>
        <button class="link" type="button" @click="emit('open-author', current.author.public_id)">{{ current.author.display_name }}</button>
        <span class="muted"> @{{ current.author.username }}</span>
      </p>
      <button v-if="current.is_own && current.status === 'draft'" class="primary" type="button" @click="publish">Опубликовать</button>
    </template>
    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>
