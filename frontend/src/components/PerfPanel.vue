<script setup>
import { ref } from "vue";
import { getSeries, startSeries, stopSeries } from "../perf.js";

defineProps({ last: { type: Object, default: null } });
const emit = defineEmits(["close"]);

const series = ref(getSeries());
const name = ref("");

function start() {
  const value = name.value.trim();
  if (!value) return;
  startSeries(value);
  series.value = value;
}

function stop() {
  stopSeries();
  series.value = "";
}
</script>

<template>
  <div class="sheet">
    <header class="card-head">
      <h3>Замеры для RAT (К2)</h3>
      <button class="icon" aria-label="Закрыть" @click="emit('close')">✕</button>
    </header>
    <p v-if="last" class="small">
      Последнее открытие: <b>{{ last.total_ms }} мс</b> до отрисовки {{ last.markers }} меток.<br />
      Страница готова: {{ last.dom_ready_ms }} мс · запрос ленты: {{ last.feed_ms }} мс · сервер:
      {{ last.server_ms ?? "—" }} мс · тип загрузки: {{ last.navigation_type }}
    </p>
    <template v-if="series">
      <p class="small">
        Идёт серия «{{ series }}». Каждое обновление страницы сохраняет замер на сервере. Первый замер серии
        (№0) — прогрев кэша.
      </p>
      <button class="secondary" @click="stop">Завершить серию</button>
    </template>
    <form v-else class="search" @submit.prevent="start">
      <input v-model="name" placeholder="Название серии, например phone-wifi-1" />
      <button class="primary">Начать</button>
    </form>
    <p class="small muted">Выгрузка всех замеров: <a href="/api/perf.csv" target="_blank">/api/perf.csv</a></p>
  </div>
</template>
