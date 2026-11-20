<script setup>
import { onBeforeUnmount, ref, watch } from "vue";
import { api } from "../api.js";

const props = defineProps({
  user: { type: Object, required: true },
});
const emit = defineEmits(["saved"]);

const displayName = ref("");
const username = ref("");
const bio = ref("");
const visibility = ref("everyone");
const theme = ref("dark");
const file = ref(null);
const preview = ref("");
const profileError = ref("");
const passwordError = ref("");
const currentPassword = ref("");
const password = ref("");
const passwordRepeat = ref("");
const busy = ref(false);

watch(
  () => props.user,
  (user) => {
    displayName.value = user.display_name;
    username.value = user.username;
    bio.value = user.bio ?? "";
    visibility.value = user.profile_visibility ?? "everyone";
    theme.value = user.theme ?? "dark";
    if (user.has_avatar) loadAvatar().catch(() => {});
  },
  { immediate: true },
);

async function loadAvatar() {
  const blob = await api.avatarBlob();
  replacePreview(URL.createObjectURL(blob));
}

function replacePreview(url) {
  if (preview.value) URL.revokeObjectURL(preview.value);
  preview.value = url;
}

function onFile(event) {
  const picked = event.target.files?.[0] ?? null;
  file.value = picked;
  if (picked) replacePreview(URL.createObjectURL(picked));
}

async function saveProfile() {
  profileError.value = "";
  busy.value = true;
  try {
    let me = await api.updateMe({
      display_name: displayName.value.trim(),
      username: username.value.trim(),
      bio: bio.value,
      profile_visibility: visibility.value,
      theme: theme.value,
    });
    if (file.value) {
      me = await api.uploadAvatar(file.value);
      file.value = null;
    }
    emit("saved", me);
  } catch (e) {
    profileError.value = e.message;
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

onBeforeUnmount(() => {
  if (preview.value) URL.revokeObjectURL(preview.value);
});
</script>

<template>
  <section class="page">
    <h2>Редактирование профиля</h2>
    <form class="stack" @submit.prevent="saveProfile">
      <img v-if="preview" class="avatar" :src="preview" alt="Фото профиля" />
      <label>Фото <input type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" @change="onFile" /></label>
      <label>Никнейм <input v-model="displayName" maxlength="100" required /></label>
      <label>Username <input v-model="username" autocapitalize="none" maxlength="50" required /></label>
      <label>Описание <textarea v-model="bio" maxlength="500" rows="3"></textarea></label>
      <button :disabled="busy">Сохранить профиль</button>
      <p v-if="profileError" class="error">{{ profileError }}</p>
    </form>

    <h2>Настройки</h2>
    <form class="stack" @submit.prevent="saveProfile">
      <label>
        Кто видит описание и фото
        <select v-model="visibility">
          <option value="everyone">Все пользователи</option>
          <option value="friends">Только друзья</option>
        </select>
      </label>
      <label>
        Тема
        <select v-model="theme">
          <option value="dark">Тёмная</option>
          <option value="light">Светлая</option>
        </select>
      </label>
      <button :disabled="busy">Сохранить настройки</button>
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
