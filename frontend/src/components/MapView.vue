<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import L from "leaflet";
import { afterPaint } from "../perf.js";

const props = defineProps({
  items: { type: Array, required: true },
  config: { type: Object, required: true },
  active: { type: Boolean, default: true },
  focus: { type: Object, default: null },
});
const emit = defineEmits(["select", "rendered"]);

const MOSCOW_CENTER = [55.751, 37.618];
const container = ref(null);
let map = null;
let markersLayer = null;

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
      .on("click", () => emit("select", item))
      .addTo(markersLayer);
  }
}

onMounted(async () => {
  map = L.map(container.value, { zoomControl: false }).setView(MOSCOW_CENTER, 11);
  L.tileLayer(props.config.tile_url, {
    maxZoom: 19,
    attribution: props.config.tile_attribution,
  }).addTo(map);
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
  <div ref="container" class="map"></div>
</template>
