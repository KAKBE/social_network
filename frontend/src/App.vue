<script setup>
import { onMounted, ref, watch } from "vue";
import { api, ApiError, getToken, setToken } from "./api.js";
import { getSeries, measureFirstRender } from "./perf.js";
import LoginView from "./components/LoginView.vue";
import MapView from "./components/MapView.vue";
import RecommendationCard from "./components/RecommendationCard.vue";
import AddView from "./components/AddView.vue";
import ListsView from "./components/ListsView.vue";
import SettingsView from "./components/SettingsView.vue";
import SearchView from "./components/SearchView.vue";
import RecommendationView from "./components/RecommendationView.vue";
import PerfPanel from "./components/PerfPanel.vue";

const TABS = [
  { id: "map", title: "Карта" },
  { id: "feed", title: "Лента" },
  { id: "add", title: "Добавить" },
  { id: "lists", title: "Списки" },
];

// Only a page load that starts already logged in is a valid K2 sample: otherwise login time is included.
const measureThisLoad = Boolean(getToken());

const user = ref(null);
const config = ref(null);
const feed = ref([]);
const unseen = ref([]);
const unseenReady = ref(false);
const cityFilter = ref("");
const authorFilter = ref("");
const friendOptions = ref([]);
const lists = ref([]);
const tab = ref("map");
const selected = ref(null);
const opened = ref(null);
const focus = ref(null);
const notice = ref("");
const loadError = ref("");
const lastPerf = ref(null);
const perfOpen = ref(false);
let feedServerMs = null;
let measured = false;

function flash(message) {
  notice.value = message;
  setTimeout(() => (notice.value = ""), 2500);
}

function logout() {
  setToken(null);
  user.value = null;
  feed.value = [];
  unseen.value = [];
  unseenReady.value = false;
  lists.value = [];
  selected.value = null;
  opened.value = null;
  document.documentElement.dataset.theme = "dark";
}

watch(
  user,
  (value) => {
    document.documentElement.dataset.theme = value?.theme === "light" ? "light" : "dark";
  },
  { immediate: true },
);

function onProfileSaved(me) {
  user.value = me;
  flash("Сохранено");
}

async function load() {
  loadError.value = "";
  try {
    const [cfg, me, feedResponse, myLists] = await Promise.all([
      api.config(),
      api.me(),
      api.feedWithTiming(),
      api.lists(),
    ]);
    feedServerMs = feedResponse.serverMs;
    config.value = cfg;
    user.value = me;
    feed.value = feedResponse.data;
    lists.value = myLists;
    if (tab.value === "feed") await ensureUnseen();
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) logout();
    else loadError.value = `Не удалось загрузить данные: ${e.message}`;
  }
}

async function onMapRendered(markers) {
  if (measured) return;
  measured = true;
  if (!measureThisLoad) return;
  const sample = measureFirstRender(markers, feedServerMs);
  lastPerf.value = sample;
  if (getSeries()) {
    await api.sendPerf(sample).catch(() => flash("Замер не сохранён на сервере"));
  }
}

async function onLoggedIn(token) {
  setToken(token);
  await load();
}

function upsertList(updated) {
  lists.value = lists.value.map((l) => (l.id === updated.id ? updated : l));
}

async function saveToList(listId, placeId) {
  try {
    const updated = await api.addToList(listId, placeId);
    upsertList(updated);
    flash(`Сохранено в «${updated.title}»`);
  } catch (e) {
    flash(e.message);
  }
}

async function removeFromList(listId, placeId) {
  upsertList(await api.removeFromList(listId, placeId));
}

async function createList(title) {
  try {
    const created = await api.createList(title);
    if (!lists.value.some((l) => l.id === created.id)) lists.value = [...lists.value, created];
  } catch (e) {
    flash(e.message);
  }
}

function openRecommendation(item) {
  opened.value = item;
  tab.value = "recommendation";
}

function onSeen(id) {
  unseen.value = unseen.value.filter((row) => row.id !== id);
}

async function ensureUnseen() {
  try {
    const [rows, myFriends] = await Promise.all([
      api.unseenFeed({ city: cityFilter.value.trim(), author: authorFilter.value }),
      friendOptions.value.length ? Promise.resolve(friendOptions.value) : api.friends(),
    ]);
    unseen.value = rows;
    friendOptions.value = myFriends;
    unseenReady.value = true;
  } catch (e) {
    flash(e.message);
  }
}

watch(tab, (value) => {
  if (value === "feed") ensureUnseen();
});

async function applyFeedFilters() {
  await ensureUnseen();
}

function onLiked(item) {
  opened.value = item;
  feed.value = feed.value.map((row) => (row.id === item.id ? item : row));
}

function showOnMap(place) {
  const item = feed.value.find((i) => i.place.id === place.id);
  selected.value = item ?? null;
  focus.value = { lat: place.lat, lon: place.lon, at: Date.now() };
  tab.value = "map";
}

function onCreated(rec) {
  feed.value = [rec, ...feed.value];
  if (rec.status === "draft") flash("Черновик сохранён");
  else if (rec.publish_at && new Date(rec.publish_at) > new Date()) flash("Рекомендация запланирована");
  else flash("Рекомендация опубликована");
  showOnMap(rec.place);
}

onMounted(() => {
  if (getToken()) load();
});
</script>

<template>
  <LoginView v-if="!user && !getToken()" @logged-in="onLoggedIn" />
  <div v-else-if="loadError" class="login">
    <p class="error">{{ loadError }}</p>
    <button @click="load">Повторить</button>
  </div>
  <div v-else-if="!user || !config" class="login"><p class="muted">Загрузка…</p></div>
  <div v-else class="app">
    <header class="topbar">
      <strong>По Следу</strong>
      <button class="badge" @click="perfOpen = !perfOpen">
        {{ lastPerf ? `${lastPerf.markers} мест · ${lastPerf.total_ms} мс` : `${feed.length} рек.` }}
      </button>
      <span class="topbar-actions">
        <button class="link small" @click="tab = 'search'">Поиск</button>
        <button class="link small" @click="tab = 'settings'">{{ user.display_name }}</button>
        <button class="link small" @click="logout">выйти</button>
      </span>
    </header>

    <main class="content">
      <section v-show="tab === 'map'" class="map-page">
        <MapView
          :items="feed"
          :config="config"
          :active="tab === 'map'"
          :focus="focus"
          @select="selected = $event"
          @open="openRecommendation"
          @rendered="onMapRendered"
        />
        <div v-if="selected" class="map-card">
          <RecommendationCard
            :key="selected.id"
            :item="selected"
            :lists="lists"
            closable
            @save="saveToList"
            @open="openRecommendation(selected)"
            @close="selected = null"
          />
        </div>
      </section>

      <section v-show="tab === 'feed'" class="page">
        <h2>Рекомендации друзей</h2>
        <form class="search" @submit.prevent="applyFeedFilters">
          <input v-model="cityFilter" maxlength="120" aria-label="Город" placeholder="Город" />
          <select v-model="authorFilter" aria-label="Автор">
            <option value="">Все авторы</option>
            <option v-for="friend in friendOptions" :key="friend.id" :value="friend.username">
              {{ friend.display_name }}
            </option>
          </select>
          <button>Показать</button>
        </form>
        <button v-if="unseenReady && !unseen.length" class="link empty-feed" @click="tab = 'add'">
          Рекомендаций нет, но вы можете добавить свою
        </button>
        <RecommendationCard
          v-for="item in unseen"
          :key="item.id"
          :item="item"
          :lists="lists"
          show-map-button
          @save="saveToList"
          @open="openRecommendation(item)"
          @show-on-map="showOnMap($event.place)"
        />
      </section>

      <AddView v-show="tab === 'add'" :config="config" :active="tab === 'add'" @created="onCreated" />

      <SearchView v-show="tab === 'search'" />
      <RecommendationView
        v-if="opened"
        :key="opened.id"
        v-show="tab === 'recommendation'"
        :item="opened"
        :lists="lists"
        @back="tab = 'feed'"
        @liked="onLiked"
        @seen="onSeen"
        @save="saveToList"
      />
      <SettingsView v-show="tab === 'settings'" :user="user" @saved="onProfileSaved" />

      <ListsView
        v-show="tab === 'lists'"
        :lists="lists"
        @create="createList"
        @remove="removeFromList"
        @show-on-map="showOnMap"
      />
    </main>

    <PerfPanel v-if="perfOpen" :last="lastPerf" @close="perfOpen = false" />
    <div v-if="notice" class="toast">{{ notice }}</div>

    <nav class="tabbar">
      <button v-for="t in TABS" :key="t.id" :class="{ active: tab === t.id }" @click="tab = t.id">
        {{ t.title }}
      </button>
    </nav>
  </div>
</template>
