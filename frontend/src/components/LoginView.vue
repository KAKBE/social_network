<script setup>
import { ref } from "vue";
import { api } from "../api.js";

const emit = defineEmits(["logged-in"]);
const mode = ref("login");
const login = ref("lesha");
const password = ref("");
const displayName = ref("");
const username = ref("");
const error = ref("");
const busy = ref(false);

function switchMode(next) {
  mode.value = next;
  error.value = "";
  password.value = "";
}

async function submit() {
  error.value = "";
  busy.value = true;
  try {
    if (mode.value === "login") {
      const { token } = await api.login(login.value.trim(), password.value);
      emit("logged-in", token);
      return;
    }
    const { token } = await api.register({
      login: login.value.trim(),
      password: password.value,
      display_name: displayName.value.trim(),
      username: username.value.trim(),
    });
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
      <label>Логин <input v-model="login" autocomplete="username" autocapitalize="none" maxlength="50" required /></label>
      <label v-if="mode === 'register'">
        Никнейм <input v-model="displayName" maxlength="100" required />
      </label>
      <label v-if="mode === 'register'">
        Username
        <input v-model="username" autocapitalize="none" maxlength="50" placeholder="если пусто — user и 8 цифр" />
      </label>
      <label>
        Пароль
        <input v-model="password" type="password" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" maxlength="128" required />
      </label>
      <p v-if="mode === 'register'" class="muted small">
        От 12 символов: заглавные и строчные буквы, цифра и специальный символ.
      </p>
      <button class="primary" :disabled="busy">{{ mode === "login" ? "Войти" : "Создать аккаунт" }}</button>
      <p v-if="error" class="error">{{ error }}</p>
    </form>
    <button v-if="mode === 'login'" class="link" type="button" @click="switchMode('register')">Зарегистрироваться</button>
    <button v-else class="link" type="button" @click="switchMode('login')">Уже есть аккаунт — войти</button>
    <p v-if="mode === 'login'" class="muted small">
      Рабочий образец. Пароль demo1234. lesha, anya, sasha, kristina, dima, masha, ira, kostya, lena, timur, vika, polina, egor, sofia, stranger1–3.
    </p>
  </main>
</template>
