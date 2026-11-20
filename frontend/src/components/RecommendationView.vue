<script setup>
import { onBeforeUnmount, ref, watch } from "vue";
import { api } from "../api.js";

const props = defineProps({
  item: { type: Object, required: true },
  lists: { type: Array, required: true },
});
const emit = defineEmits(["back", "liked", "seen", "to-list"]);

const current = ref(props.item);
const profile = ref(null);
const error = ref("");
const photoUrls = ref([]);

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
  profile.value = null;
  error.value = "";
  try {
    current.value = await api.recommendation(item.id);
    emit("seen", item.id);
  } catch (err) {
    error.value = err.message;
  }
}

watch(
  () => props.item.id,
  () => {
    openPage(props.item);
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

async function openAuthor() {
  error.value = "";
  try {
    profile.value = await api.profile(current.value.author.public_id);
  } catch (err) {
    error.value = err.message;
  }
}
</script>

<template>
  <section class="page">
    <button class="link" @click="emit('back')">Назад</button>
    <h2>{{ current.place.name }}</h2>
    <p v-if="current.place.address" class="muted">{{ current.place.address }}</p>
    <p v-if="current.text">{{ current.text }}</p>
    <div v-if="photoUrls.length" class="photo-row">
      <img v-for="url in photoUrls" :key="url" :src="url" alt="Фото места" />
    </div>
    <label v-if="current.is_own && (current.photos?.length ?? 0) < 5">
      Фото
      <input type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" @change="addPhoto" />
    </label>
    <p>
      <button class="link" @click="openAuthor">{{ current.author.display_name }}</button>
      <span class="muted"> @{{ current.author.username }}</span>
    </p>
    <button v-if="current.is_own && current.status === 'draft'" @click="publish">Опубликовать</button>
    <button @click="like">{{ current.liked ? "Убрать лайк" : "Лайк" }} · {{ current.like_count }}</button>
    <article v-if="profile" class="card">
      <h3>{{ profile.display_name }}</h3>
      <p class="muted">@{{ profile.username }}</p>
      <p v-if="profile.bio">{{ profile.bio }}</p>
      <p v-else class="muted">Описание скрыто или не заполнено.</p>
    </article>
    <button @click="emit('to-list', current.place)">В список</button>
    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>
