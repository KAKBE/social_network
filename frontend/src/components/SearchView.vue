<script setup>
import { onMounted, ref } from "vue";
import { api } from "../api.js";

const emit = defineEmits(["open-profile"]);

const query = ref("");
const results = ref([]);
const requests = ref([]);
const error = ref("");
const busy = ref(false);

const relationText = {
  none: "",
  outgoing: "Заявка отправлена",
  incoming: "Хочет добавить вас",
  friend: "Уже в друзьях",
};

onMounted(() => {
  loadRequests().catch((err) => {
    error.value = err.message;
  });
});

async function loadRequests() {
  requests.value = await api.friendRequests();
}

async function search() {
  error.value = "";
  const term = query.value.trim();
  if (!term) return;
  busy.value = true;
  try {
    results.value = await api.searchUsers(term);
  } catch (err) {
    results.value = [];
    error.value = err.message;
  } finally {
    busy.value = false;
  }
}

function markRelation(username, relation) {
  results.value = results.value.map((item) => (item.username === username ? { ...item, relation } : item));
}

function markClose(username, isClose) {
  results.value = results.value.map((item) => (item.username === username ? { ...item, is_close: isClose } : item));
}

async function setClose(username, isClose) {
  error.value = "";
  try {
    await api.setCloseFriend(username, isClose);
    markClose(username, isClose);
  } catch (err) {
    error.value = err.message;
  }
}

async function addFriend(username) {
  error.value = "";
  try {
    await api.sendFriendRequest(username);
    markRelation(username, "outgoing");
  } catch (err) {
    error.value = err.message;
  }
}

async function accept(request) {
  error.value = "";
  try {
    await api.acceptFriendRequest(request.id);
    await loadRequests();
    markRelation(request.username, "friend");
  } catch (err) {
    error.value = err.message;
  }
}

async function reject(request) {
  error.value = "";
  try {
    await api.rejectFriendRequest(request.id);
    await loadRequests();
    markRelation(request.username, "none");
  } catch (err) {
    error.value = err.message;
  }
}
</script>

<template>
  <section class="page">
    <h2>Поиск</h2>
    <form class="stack" @submit.prevent="search">
      <label>Username <input v-model="query" autocapitalize="none" maxlength="50" required /></label>
      <button :class="{ primary: !requests.length }" :disabled="busy">Найти</button>
    </form>
    <p v-if="error" class="error">{{ error }}</p>

    <article v-for="item in results" :key="item.public_id" class="card">
      <header class="card-head">
        <button class="link" @click="emit('open-profile', item.public_id)">{{ item.display_name }}</button>
        <span class="muted small">@{{ item.username }}</span>
      </header>
      <p v-if="relationText[item.relation]" class="muted">{{ relationText[item.relation] }}</p>
      <button v-if="item.relation === 'none'" @click="addFriend(item.username)">Добавить в друзья</button>
      <button v-if="item.relation === 'friend'" @click="setClose(item.username, !item.is_close)">
        {{ item.is_close ? "Убрать из близких" : "В близкие друзья" }}
      </button>
    </article>

    <h2>Входящие заявки</h2>
    <p v-if="!requests.length" class="muted">Заявок нет.</p>
    <article v-for="request in requests" :key="request.id" class="card">
      <p>{{ request.display_name }} <span class="muted">@{{ request.username }}</span></p>
      <button class="primary" @click="accept(request)">Принять</button>
      <button @click="reject(request)">Отклонить</button>
    </article>
  </section>
</template>
