<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { api } from "../api.js";
import { categoryLabel } from "../categories.js";
import Icon from "./Icon.vue";

const props = defineProps({
  item: { type: Object, required: true },
  lists: { type: Array, required: true },
  showMapButton: { type: Boolean, default: false },
  showListButton: { type: Boolean, default: true },
  closable: { type: Boolean, default: false },
});
const emit = defineEmits(["show-on-map", "close", "open", "to-list", "open-author", "edit"]);

const savedIn = computed(() =>
  props.lists.filter((l) => l.places.some((p) => p.id === props.item.place.id)).map((l) => l.title),
);
const date = computed(() => new Date(props.item.created_at).toLocaleDateString("ru-RU"));
const photoUrl = ref("");
const menu = ref(false);
const root = ref(null);
let objectUrl = "";
let photoGeneration = 0;

function releasePhoto() {
  if (objectUrl) URL.revokeObjectURL(objectUrl);
  objectUrl = "";
  photoUrl.value = "";
}

async function loadPhoto() {
  const generation = ++photoGeneration;
  const photo = props.item.photos?.[0];
  if (!photo) {
    if (generation === photoGeneration) releasePhoto();
    return;
  }
  const blob = await api.recommendationPhotoBlob(props.item.id, photo.id);
  if (generation !== photoGeneration) return;
  releasePhoto();
  objectUrl = URL.createObjectURL(blob);
  photoUrl.value = objectUrl;
}

function onDocumentPointer(event) {
  if (menu.value && root.value && !root.value.contains(event.target)) menu.value = false;
}

function openFromCard(event) {
  if (event.target.closest("button, a, input, select, textarea, label")) return;
  menu.value = false;
  emit("open");
}

function editFromMenu() {
  menu.value = false;
  emit("edit");
}

onMounted(() => {
  document.addEventListener("pointerdown", onDocumentPointer);
});
watch(
  () => props.item,
  () => {
    loadPhoto().catch(() => {});
  },
  { immediate: true },
);
onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onDocumentPointer);
  releasePhoto();
});
</script>

<template>
  <article ref="root" class="card post-card" @click="openFromCard">
    <header class="card-head">
      <div>
        <h3>
          <button class="link title" type="button" @click="emit('open')">{{ item.place.name }}</button>
        </h3>
        <p class="muted">
          <template v-if="item.is_own">Ваша рекомендация</template>
          <button v-else class="link small" type="button" @click="emit('open-author', item.author.public_id)">
            {{ item.author.display_name }}
          </button>
          · {{ date }}
          <template v-if="categoryLabel(item.category)"> · {{ categoryLabel(item.category) }}</template>
        </p>
      </div>
      <div class="card-tools">
        <button
          v-if="showMapButton"
          class="icon"
          type="button"
          aria-label="На карте"
          @click="emit('show-on-map', item)"
        >
          <Icon name="pin" />
        </button>
        <button
          v-if="showListButton"
          class="icon"
          :class="{ saved: savedIn.length }"
          type="button"
          :aria-label="savedIn.length ? 'В избранном' : 'В избранное'"
          :aria-pressed="savedIn.length > 0"
          @click="emit('to-list', item.place)"
        >
          <Icon :name="savedIn.length ? 'bookmark-filled' : 'bookmark'" />
        </button>
        <button
          v-if="item.is_own"
          class="icon"
          type="button"
          aria-label="Ещё"
          :aria-expanded="menu"
          @click="menu = !menu"
        >
          <Icon name="more" />
        </button>
        <button v-if="closable" class="icon" type="button" aria-label="Закрыть" @click="emit('close')">
          <Icon name="x" />
        </button>
        <div v-if="menu" class="card-menu">
          <button type="button" @click="editFromMenu">Изменить</button>
        </div>
      </div>
    </header>
    <img v-if="photoUrl" class="place-photo" :src="photoUrl" alt="Фото места" />
    <p v-if="item.place.city" class="muted">{{ item.place.city }}</p>
    <p class="card-text">{{ item.text }}</p>
    <p v-if="savedIn.length" class="saved">Сохранено: {{ savedIn.join(", ") }}</p>
  </article>
</template>
