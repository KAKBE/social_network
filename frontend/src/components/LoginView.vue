<script setup>
import { ref } from "vue";
import { api } from "../api.js";

const emit = defineEmits(["logged-in"]);
const username = ref("lesha");
const password = ref("");
const error = ref("");
const busy = ref(false);

async function submit() {
  error.value = "";
  busy.value = true;
  try {
    const { token } = await api.login(username.value.trim(), password.value);
    emit("logged-in", token);
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <main class="login">
    <h1>По Следу</h1>
    <p class="muted">Места, которые советуют ваши друзья</p>
    <form @submit.prevent="submit">
      <label>Логин <input v-model="username" autocomplete="username" autocapitalize="none" /></label>
      <label>Пароль <input v-model="password" type="password" autocomplete="current-password" /></label>
      <button :disabled="busy">Войти</button>
      <p v-if="error" class="error">{{ error }}</p>
    </form>
    <p class="muted small">
      Рабочий образец. Тестовые пользователи: lesha, anya, sasha, kristina, dima, masha, stranger1–3.
    </p>
  </main>
</template>
