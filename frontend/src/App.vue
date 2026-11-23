<script setup>
import { onMounted, onUnmounted, ref, watch } from "vue";
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
import ProfileView from "./components/ProfileView.vue";
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
const profileId = ref("");
const profileReturn = ref("feed");
const profileStack = ref([]);
const openedFrom = ref("feed");
const selected = ref(null);
const opened = ref(null);
const pendingPlace = ref(null);
const focus = ref(null);
const notice = ref("");
const loadError = ref("");
const lastPerf = ref(null);
const perfOpen = ref(false);
const notes = ref([]);
const unread = ref(0);
let feedServerMs = null;
let measured = false;
let poll = 0;

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
  friendOptions.value = [];
  cityFilter.value = "";
  authorFilter.value = "";
  selected.value = null;
  opened.value = null;
  pendingPlace.value = null;
  profileId.value = "";
  profileStack.value = [];
  tab.value = "map";
  lastPerf.value = null;
  notes.value = [];
  unread.value = 0;
  clearInterval(poll);
  document.documentElement.dataset.theme = "dark";
}

async function refreshNotes() {
  const data = await api.notifications();
  notes.value = data.items;
  unread.value = data.unread;
}

function startPoll() {
  clearInterval(poll);
  poll = setInterval(() => {
    refreshNotes().catch(() => {});
  }, 10000);
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
    await refreshNotes();
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
  startPoll();
}

async function openNote(item) {
  try {
    const data = await api.readNotification(item.id);
    notes.value = data.items;
    unread.value = data.unread;
    openRecommendation(await api.recommendation(item.recommendation_id));
  } catch (e) {
    flash(e.message);
  }
}

function upsertList(updated) {
  lists.value = lists.value.map((l) => (l.id === updated.id ? updated : l));
}

async function saveToList(listId, placeId) {
  try {
    const updated = await api.addToList(listId, placeId);
    upsertList(updated);
    flash(`Сохранено в «${updated.title}»`);
    return true;
  } catch (e) {
    flash(e.message);
    return false;
  }
}

async function removeFromList(listId, itemId) {
  upsertList(await api.removeFromList(listId, itemId));
}

function openListPicker(place) {
  pendingPlace.value = place;
  tab.value = "lists";
}

async function confirmListAdd(listId) {
  if (!pendingPlace.value?.id) return;
  const saved = await saveToList(listId, pendingPlace.value.id);
  if (saved) pendingPlace.value = null;
}

async function createList(title) {
  try {
    const created = await api.createList(title);
    if (!lists.value.some((l) => l.id === created.id)) lists.value = [...lists.value, created];
  } catch (e) {
    flash(e.message);
  }
}

function openProfile(publicId) {
  const insideProfile =
    tab.value === "profile" ||
    (tab.value === "recommendation" && openedFrom.value === "profile") ||
    (tab.value === "settings" && profileId.value);
  if (profileId.value === publicId) {
    tab.value = "profile";
    return;
  }
  if (insideProfile && profileId.value) {
    profileStack.value = [...profileStack.value, profileId.value];
  } else {
    profileReturn.value = tab.value;
    profileStack.value = [];
  }
  profileId.value = publicId;
  tab.value = "profile";
}

function closeProfile() {
  const previous = profileStack.value.at(-1);
  if (previous) {
    profileStack.value = profileStack.value.slice(0, -1);
    profileId.value = previous;
    return;
  }
  tab.value = profileReturn.value || "feed";
}

function openRecommendation(item) {
  openedFrom.value = tab.value === "profile" ? "profile" : tab.value;
  opened.value = item;
  tab.value = "recommendation";
}

function closeRecommendation() {
  tab.value = openedFrom.value || "feed";
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

async function onLiked(item) {
  opened.value = item;
  feed.value = feed.value.map((row) => (row.id === item.id ? item : row));
  unseen.value = unseen.value.map((row) => (row.id === item.id ? item : row));
  if (selected.value?.id === item.id) selected.value = item;
  try {
    lists.value = await api.lists();
  } catch (e) {
    flash(e.message);
  }
}

async function onDeleted(id) {
  feed.value = feed.value.filter((row) => row.id !== id);
  unseen.value = unseen.value.filter((row) => row.id !== id);
  if (selected.value?.id === id) selected.value = null;
  if (opened.value?.id === id) opened.value = null;
  tab.value = "feed";
  try {
    lists.value = await api.lists();
  } catch (e) {
    flash(e.message);
  }
  flash("Рекомендация удалена");
}

function showOnMap(place) {
  const item = !place.limited && place.id ? feed.value.find((i) => i.place.id === place.id) : null;
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
  if (getToken()) {
    load();
    startPoll();
  }
});

onUnmounted(() => clearInterval(poll));
</script>

<template>
  <LoginView v-if="!user && !getToken()" @logged-in="onLoggedIn" />
  <div v-else-if="loadError" class="login">
    <p class="error">{{ loadError }}</p>
    <button class="primary" @click="load">Повторить</button>
  </div>
  <div v-else-if="!user || !config" class="login"><p class="muted">Загрузка…</p></div>
  <div v-else class="app">
    <header class="topbar">
      <button class="icon bell" :aria-label="unread ? `Уведомления, ${unread}` : 'Уведомления'" @click="tab = 'notifications'">
        <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
          <path
            fill="currentColor"
            d="M12 3a5 5 0 0 0-5 5v2.1c0 .8-.3 1.6-.8 2.2L4.6 14.4A1 1 0 0 0 5.4 16h13.2a1 1 0 0 0 .8-1.6l-1.6-2.1a3.2 3.2 0 0 1-.8-2.2V8a5 5 0 0 0-5-5zm0 18a2.5 2.5 0 0 0 2.4-2h-4.8A2.5 2.5 0 0 0 12 21z"
          />
        </svg>
        <span v-if="unread" class="bell-count">{{ unread }}</span>
      </button>
      <strong>По Следу</strong>
      <button class="badge" @click="perfOpen = !perfOpen">
        {{ feed.length }} рек.
      </button>
      <span class="topbar-actions">
        <button class="link small" @click="tab = 'search'">Поиск</button>
        <button class="link small" @click="openProfile(user.public_id)">{{ user.display_name }}</button>
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
            @to-list="openListPicker"
            @open="openRecommendation(selected)"
            @open-author="openProfile"
            @close="selected = null"
          />
        </div>
      </section>

      <section v-show="tab === 'notifications'" class="page">
        <h2>Уведомления</h2>
        <p v-if="!notes.length" class="muted">Уведомлений нет.</p>
        <button v-for="item in notes" :key="item.id" class="note" @click="openNote(item)">
          {{ item.author_name }}: новая рекомендация «{{ item.place_name }}»
        </button>
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
          <button class="primary">Показать</button>
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
          @to-list="openListPicker"
          @open="openRecommendation(item)"
          @open-author="openProfile"
          @show-on-map="showOnMap($event.place)"
        />
      </section>

      <AddView v-show="tab === 'add'" :config="config" :active="tab === 'add'" @created="onCreated" />

      <SearchView v-show="tab === 'search'" @open-profile="openProfile" />
      <ProfileView
        v-if="profileId"
        v-show="tab === 'profile'"
        :public-id="profileId"
        :active="tab === 'profile'"
        :lists="lists"
        @back="closeProfile"
        @open="openRecommendation"
        @open-profile="openProfile"
        @to-list="openListPicker"
        @settings="tab = 'settings'"
        @saved="onProfileSaved"
        @add="tab = 'add'"
        @show-on-map="showOnMap($event.place)"
      />
      <RecommendationView
        v-if="opened"
        :key="opened.id"
        v-show="tab === 'recommendation'"
        :item="opened"
        :lists="lists"
        @back="closeRecommendation"
        @open-author="openProfile"
        @liked="onLiked"
        @deleted="onDeleted"
        @seen="onSeen"
        @to-list="openListPicker"
      />
      <SettingsView v-show="tab === 'settings'" :user="user" @saved="onProfileSaved" />

      <ListsView
        v-show="tab === 'lists'"
        :lists="lists"
        :pending="pendingPlace"
        @create="createList"
        @add="confirmListAdd"
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
