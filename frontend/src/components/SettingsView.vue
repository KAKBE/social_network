<script setup>
import { ref, watch } from "vue";
import { api } from "../api.js";

const props = defineProps({
  user: { type: Object, required: true },
});
const emit = defineEmits(["saved"]);

const theme = ref("dark");
const settingsError = ref("");
const passwordError = ref("");
const currentPassword = ref("");
const password = ref("");
const passwordRepeat = ref("");
const busy = ref(false);

watch(
  () => props.user,
  (user) => {
    theme.value = user.theme ?? "dark";
  },
  { immediate: true },
);

async function saveTheme() {
  settingsError.value = "";
  busy.value = true;
  try {
    emit("saved", await api.updateMe({ theme: theme.value }));
  } catch (e) {
    settingsError.value = e.message;
  } finally {
    busy.value = false;
  }
}

async function savePassword() {
  passwordError.value = "";
  busy.value = true;
  try {
    await api.changePassword({
      current_password: currentPassword.value,
      password: password.value,
      password_repeat: passwordRepeat.value,
    });
    currentPassword.value = password.value = passwordRepeat.value = "";
    emit("saved", props.user);
  } catch (e) {
    passwordError.value = e.message;
  } finally {
    busy.value = false;
  }
}

</script>

<template>
  <section class="page">
    <h2>Настройки</h2>
    <form class="stack" @submit.prevent="saveTheme">
      <label>
        Тема
        <select v-model="theme">
          <option value="dark">Тёмная</option>
          <option value="light">Светлая</option>
        </select>
      </label>
      <button class="primary" :disabled="busy">Сохранить настройки</button>
      <p v-if="settingsError" class="error">{{ settingsError }}</p>
    </form>

    <h2>Пароль</h2>
    <form class="stack" @submit.prevent="savePassword">
      <label>Текущий пароль <input v-model="currentPassword" type="password" autocomplete="current-password" required /></label>
      <label>Новый пароль <input v-model="password" type="password" autocomplete="new-password" required /></label>
      <label>Новый пароль ещё раз <input v-model="passwordRepeat" type="password" autocomplete="new-password" required /></label>
      <p class="muted small">От 12 символов: заглавные и строчные буквы, цифра и специальный символ.</p>
      <button :disabled="busy">Сменить пароль</button>
      <p v-if="passwordError" class="error">{{ passwordError }}</p>
    </form>
  </section>
</template>
