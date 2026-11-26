<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import L from "leaflet";
import { afterPaint } from "../perf.js";

const props = defineProps({
  items: { type: Array, required: true },
  config: { type: Object, required: true },
  active: { type: Boolean, default: true },
  focus: { type: Object, default: null },
  embedded: { type: Boolean, default: false },
  fit: { type: Boolean, default: false },
});
const emit = defineEmits(["select", "open", "rendered"]);

const MOSCOW_CENTER = [55.751, 37.618];
const container = ref(null);
let map = null;
let markersLayer = null;

function bubble(item) {
  const root = document.createElement("div");
  const place = document.createElement("strong");
  place.textContent = item.place.name;
  const author = document.createElement("div");
  author.textContent = item.author.display_name;
  const open = document.createElement("button");
  open.type = "button";
  open.textContent = "Открыть";
  open.addEventListener("click", () => emit("open", item));
  root.append(place, author, open);
  return root;
}

function drawMarkers(items) {
  markersLayer.clearLayers();
  for (const item of items) {
    L.circleMarker([item.place.lat, item.place.lon], {
      radius: 9,
      weight: 2,
      color: "#ffffff",
      fillColor: item.is_own ? "#2f6fed" : "#c6f135",
      fillOpacity: 1,
    })
      .bindPopup(bubble(item))
      .addTo(markersLayer);
  }
  if (props.fit && items.length) {
    const bounds = L.latLngBounds(items.map((item) => [item.place.lat, item.place.lon]));
    map.fitBounds(bounds.pad(0.25), { maxZoom: 15, animate: false });
  }
}

onMounted(async () => {
  map = L.map(container.value, { zoomControl: false, attributionControl: false }).setView(MOSCOW_CENTER, 11);
  L.tileLayer(props.config.tile_url, { maxZoom: 19 }).addTo(map);
  markersLayer = L.layerGroup().addTo(map);
  drawMarkers(props.items);
  await afterPaint();
  emit("rendered", props.items.length);
});

onBeforeUnmount(() => map?.remove());

watch(
  () => props.items,
  (items) => map && drawMarkers(items),
);

watch(
  () => props.active,
  (active) => active && map && setTimeout(() => map.invalidateSize(), 0),
);

watch(
  () => props.focus,
  (focus) => focus && map?.setView([focus.lat, focus.lon], 15),
);
</script>

<template>
  <div ref="container" class="map" :class="{ embedded }"></div>
</template>
