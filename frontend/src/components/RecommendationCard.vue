<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { api } from "../api.js";

const props = defineProps({
  item: { type: Object, required: true },
  lists: { type: Array, required: true },
  showMapButton: { type: Boolean, default: false },
  closable: { type: Boolean, default: false },
});
const emit = defineEmits(["show-on-map", "close", "open", "to-list"]);

const savedIn = computed(() =>
  props.lists.filter((l) => l.places.some((p) => p.id === props.item.place.id)).map((l) => l.title),
);
const date = computed(() => new Date(props.item.created_at).toLocaleDateString("ru-RU"));
const photoUrl = ref("");
let objectUrl = "";

function releasePhoto() {
  if (objectUrl) URL.revokeObjectURL(objectUrl);
  objectUrl = "";
  photoUrl.value = "";
}

async function loadPhoto() {
  releasePhoto();
  const photo = props.item.photos?.[0];
  if (!photo) return;
  const blob = await api.recommendationPhotoBlob(props.item.id, photo.id);
  objectUrl = URL.createObjectURL(blob);
  photoUrl.value = objectUrl;
}

onMounted(() => {
  loadPhoto().catch(() => {});
});
watch(
  () => props.item.photos?.[0]?.id,
  () => {
    loadPhoto().catch(() => {});
  },
);
onBeforeUnmount(releasePhoto);
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
    <img v-if="photoUrl" class="place-photo" :src="photoUrl" alt="Фото места" />
    <p v-if="item.place.city" class="muted">{{ item.place.city }}</p>
    <p class="card-text">{{ item.text }}</p>
    <p v-if="savedIn.length" class="saved">Сохранено: {{ savedIn.join(", ") }}</p>
    <div class="card-actions">
      <button class="secondary" @click="emit('open')">Открыть</button>
      <button v-if="showMapButton" class="secondary" @click="emit('show-on-map', item)">На карте</button>
      <button @click="emit('to-list', item.place)">В список</button>
    </div>
  </article>
</template>
