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
const address = ref("");
const name = ref("");
const text = ref("");
const error = ref("");
const saving = ref(false);

const container = ref(null);
let map = null;
let pin = null;

function setPoint(lat, lon) {
  point.value = { lat, lon };
  if (pin) pin.setLatLng([lat, lon]);
  else pin = L.circleMarker([lat, lon], { radius: 10, color: "#fff", weight: 2, fillColor: "#2f6fed", fillOpacity: 1 }).addTo(map);
  map.setView([lat, lon], Math.max(map.getZoom(), 15));
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

function choose(result) {
  address.value = result.display_name;
  if (!name.value) name.value = result.display_name.split(",")[0];
  results.value = [];
  setPoint(result.lat, result.lon);
}

async function publish() {
  error.value = "";
  if (!point.value) {
    error.value = "Выберите адрес или отметьте место на карте";
    return;
  }
  saving.value = true;
  try {
    const rec = await api.createRecommendation({
      name: name.value.trim(),
      address: address.value,
      lat: point.value.lat,
      lon: point.value.lon,
      text: text.value.trim(),
    });
    query.value = address.value = name.value = text.value = "";
    point.value = null;
    pin?.remove();
    pin = null;
    emit("created", rec);
  } catch (e) {
    error.value = e.message;
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  map = L.map(container.value, { zoomControl: false }).setView([55.751, 37.618], 11);
  L.tileLayer(props.config.tile_url, { maxZoom: 19, attribution: props.config.tile_attribution }).addTo(map);
  map.on("click", (e) => {
    address.value = "";
    setPoint(e.latlng.lat, e.latlng.lng);
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
    <form class="stack" @submit.prevent="publish">
      <label>Название <input v-model="name" maxlength="200" required /></label>
      <label>
        Рекомендация
        <textarea v-model="text" rows="4" maxlength="2000" required placeholder="Чем место хорошо? Можно описать готовый план встречи."></textarea>
      </label>
      <button :disabled="saving">Опубликовать для друзей</button>
      <p v-if="error" class="error">{{ error }}</p>
    </form>
  </section>
</template>
