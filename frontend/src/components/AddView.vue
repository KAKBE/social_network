<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import L from "leaflet";
import { api } from "../api.js";

const props = defineProps({
  config: { type: Object, required: true },
  active: { type: Boolean, default: true },
});
const emit = defineEmits(["created"]);

const query = ref("");
const results = ref([]);
const searchMessage = ref("");
const searching = ref(false);
const point = ref(null);
const pointFromAddress = ref(false);
const pointCorrected = ref(false);
const address = ref("");
const city = ref("");
const name = ref("");
const text = ref("");
const error = ref("");
const saving = ref(false);
const friends = ref([]);
const visibility = ref("friends");
const audience = ref([]);
const files = ref([]);
const lists = ref([]);
const listId = ref("");
const draft = ref(false);
const publishAt = ref("");

const container = ref(null);
let map = null;
let pin = null;

const pinIcon = L.divIcon({ className: "pin", iconSize: [18, 18], iconAnchor: [9, 9] });

function onDrag() {
  const latlng = pin.getLatLng();
  const hadAddress = Boolean(address.value);
  point.value = { lat: latlng.lat, lon: latlng.lng };
  if (hadAddress) pointCorrected.value = true;
  pointFromAddress.value = false;
  showAddress(latlng.lat, latlng.lng);
}

function setPoint(lat, lon) {
  point.value = { lat, lon };
  if (pin) pin.setLatLng([lat, lon]);
  else {
    pin = L.marker([lat, lon], { icon: pinIcon, draggable: true }).addTo(map);
    pin.on("dragend", onDrag);
  }
  map.setView([lat, lon], Math.max(map.getZoom(), 15));
}

async function showAddress(lat, lon) {
  try {
    const response = await api.reverse(lat, lon);
    if (response.address) {
      address.value = response.address;
      city.value = response.city || "";
    }
  } catch (error) {
    city.value = "";
    searchMessage.value = error.message;
  }
}

// Search runs only on an explicit button press: the Nominatim policy forbids search-as-you-type.
async function search() {
  searchMessage.value = "";
  results.value = [];
  searching.value = true;
  try {
    const response = await api.geocode(query.value.trim());
    results.value = response.results;
    if (!response.results.length) searchMessage.value = "Ничего не найдено, отметьте место на карте";
  } catch (e) {
    searchMessage.value = e.message;
  } finally {
    searching.value = false;
  }
}

function onFiles(event) {
  files.value = [...event.target.files].slice(0, 5);
}

function choose(result) {
  address.value = result.display_name;
  city.value = result.city || "";
  if (!name.value) name.value = result.display_name.split(",")[0];
  results.value = [];
  setPoint(result.lat, result.lon);
  pointFromAddress.value = true;
  pointCorrected.value = false;
}

async function publish() {
  error.value = "";
  if (!point.value) {
    error.value = "Выберите адрес или отметьте место на карте";
    return;
  }
  saving.value = true;
  try {
    let rec = await api.createRecommendation({
      name: name.value.trim(),
      address: address.value,
      lat: point.value.lat,
      lon: point.value.lon,
      text: text.value.trim(),
      point_corrected: pointCorrected.value,
      city: city.value,
      visibility: visibility.value,
      audience: visibility.value === "allow" || visibility.value === "deny" ? audience.value : [],
      draft: draft.value,
      publish_at: !draft.value && publishAt.value ? new Date(publishAt.value).toISOString() : null,
      list_id: listId.value ? Number(listId.value) : null,
    });
    for (const file of files.value) rec = await api.uploadRecommendationPhoto(rec.id, file);
    query.value = address.value = city.value = name.value = text.value = "";
    visibility.value = "friends";
    audience.value = [];
    files.value = [];
    draft.value = false;
    publishAt.value = "";
    listId.value = "";
    point.value = null;
    pointFromAddress.value = false;
    pointCorrected.value = false;
    pin?.remove();
    pin = null;
    emit("created", rec);
  } catch (e) {
    error.value = e.message;
  } finally {
    saving.value = false;
  }
}

async function loadFriends() {
  friends.value = await api.friends();
  lists.value = await api.lists();
}

onMounted(() => {
  loadFriends().catch(() => {});
  map = L.map(container.value, { zoomControl: false }).setView([55.751, 37.618], 11);
  L.tileLayer(props.config.tile_url, { maxZoom: 19, attribution: props.config.tile_attribution }).addTo(map);
  map.on("click", (e) => {
    const hadAddress = Boolean(address.value);
    setPoint(e.latlng.lat, e.latlng.lng);
    if (hadAddress) pointCorrected.value = true;
    pointFromAddress.value = false;
    showAddress(e.latlng.lat, e.latlng.lng);
  });
});

onBeforeUnmount(() => map?.remove());

watch(
  () => props.active,
  (active) => active && map && setTimeout(() => map.invalidateSize(), 0),
);
</script>

<template>
  <section class="page">
    <h2>Новая рекомендация</h2>
    <form class="search" @submit.prevent="search">
      <input v-model="query" placeholder="Адрес, например: Москва, Таллинская улица, 34" />
      <button :disabled="searching || query.trim().length < 3">Найти</button>
    </form>
    <p v-if="searchMessage" class="muted">{{ searchMessage }}</p>
    <ul v-if="results.length" class="results">
      <li v-for="r in results" :key="`${r.lat},${r.lon}`">
        <button class="link" @click="choose(r)">{{ r.display_name }}</button>
      </li>
    </ul>
    <p class="muted small">Или нажмите на карту, чтобы отметить место вручную.</p>
    <div ref="container" class="mini-map"></div>
    <p v-if="pointFromAddress" class="muted small">
      Точка найдена по адресу и может отличаться от места на сотни метров. Проверьте её и при необходимости нажмите на карту, чтобы поправить.
    </p>
    <form class="stack" @submit.prevent="publish">
      <label>Название <input v-model="name" maxlength="200" required /></label>
      <label>
        Рекомендация
        <textarea v-model="text" rows="4" maxlength="2000" required placeholder="Чем место хорошо? Можно описать готовый план встречи."></textarea>
      </label>
      <label>
        Кто видит
        <select v-model="visibility">
          <option value="friends">Друзья</option>
          <option value="close">Близкие друзья</option>
          <option value="allow">Только выбранные друзья</option>
          <option value="deny">Все друзья, кроме выбранных</option>
        </select>
      </label>
      <fieldset v-if="visibility === 'allow' || visibility === 'deny'">
        <legend>Друзья</legend>
        <label v-for="friend in friends" :key="friend.id">
          <input v-model="audience" type="checkbox" :value="friend.username" />
          {{ friend.display_name }} @{{ friend.username }}
        </label>
      </fieldset>
      <label>
        Список
        <select v-model="listId">
          <option value="">Не добавлять</option>
          <option v-for="list in lists" :key="list.id" :value="String(list.id)">{{ list.title }}</option>
        </select>
      </label>
      <label><input v-model="draft" type="checkbox" /> Сохранить как черновик</label>
      <label v-if="!draft">
        Опубликовать в
        <input v-model="publishAt" type="datetime-local" />
      </label>
      <label>
        Фото, до 5
        <input type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" multiple @change="onFiles" />
      </label>
      <button :disabled="saving">Опубликовать для друзей</button>
      <p v-if="error" class="error">{{ error }}</p>
    </form>
  </section>
</template>
