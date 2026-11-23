<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { api } from "../api.js";
import { PLACE_CATEGORIES, categoryLabel } from "../categories.js";
import { canOpenProfileMap, postsForChip } from "../profileMap.js";
import MapView from "./MapView.vue";
import RecommendationCard from "./RecommendationCard.vue";

const props = defineProps({
  publicId: { type: String, required: true },
  lists: { type: Array, required: true },
  config: { type: Object, required: true },
  active: { type: Boolean, default: true },
});
const emit = defineEmits(["back", "open", "edit", "open-profile", "to-list", "settings", "saved", "add", "show-on-map", "managed"]);

const page = ref(null);
const posts = ref([]);
const error = ref("");
const chip = ref("all");
const showMap = ref(false);
const categoryVisibility = ref("friends");
const categoryBusy = ref(false);
const editing = ref(false);
const showAllFriends = ref(false);
const busy = ref(false);
const displayName = ref("");
const surname = ref("");
const username = ref("");
const bio = ref("");
const visibility = ref("everyone");
const ownFace = ref("");
const faces = ref({});

let ownUrl = "";
const faceUrls = {};

const fullName = computed(() => [page.value?.display_name, page.value?.surname].filter(Boolean).join(" "));
const letter = computed(() => (page.value?.display_name || "?").trim().charAt(0).toUpperCase());
const shownFriends = computed(() => {
  const friends = page.value?.friends ?? [];
  return showAllFriends.value ? friends : friends.slice(0, 6);
});
const usedCategories = computed(() =>
  PLACE_CATEGORIES.filter((item) => posts.value.some((post) => post.category === item.id && post.status !== "draft")),
);
const hasDrafts = computed(() => posts.value.some((post) => post.status === "draft"));
const publishedCount = computed(() => posts.value.filter((post) => post.status !== "draft").length);
const visiblePosts = computed(() => postsForChip(posts.value, chip.value));
const canMap = computed(() => canOpenProfileMap(posts.value, chip.value));
const categoryPosts = computed(() => posts.value.filter((post) => post.category === chip.value));
const categoryDraftCount = computed(() => categoryPosts.value.filter((post) => post.status === "draft").length);
const categoryHidden = computed(
  () => categoryPosts.value.length > 0 && categoryPosts.value.every((post) => post.visibility === "self"),
);

function releaseFaces() {
  if (ownUrl) URL.revokeObjectURL(ownUrl);
  ownUrl = "";
  ownFace.value = "";
  for (const url of Object.values(faceUrls)) URL.revokeObjectURL(url);
  for (const key of Object.keys(faceUrls)) delete faceUrls[key];
  faces.value = {};
}

async function loadFace(person, seq) {
  if (!person.has_avatar || faceUrls[person.public_id]) return;
  const blob = await api.userAvatar(person.public_id);
  if (seq !== loadSeq) return;
  faceUrls[person.public_id] = URL.createObjectURL(blob);
  faces.value = { ...faces.value, [person.public_id]: faceUrls[person.public_id] };
}

let loadSeq = 0;

async function load() {
  const seq = ++loadSeq;
  const requested = props.publicId;
  const stale = () => seq !== loadSeq || requested !== props.publicId;
  error.value = "";
  releaseFaces();
  const [profile, recommendations] = await Promise.all([
    api.profile(requested),
    api.profileRecommendations(requested),
  ]);
  if (stale()) return;
  let nextVisibility = visibility.value;
  let nextFace = "";
  if (profile.is_self) {
    const me = await api.me();
    if (stale()) return;
    nextVisibility = me.profile_visibility;
    if (me.has_avatar) {
      const blob = await api.avatarBlob();
      if (stale()) return;
      nextFace = URL.createObjectURL(blob);
    }
  } else if (profile.has_avatar) {
    const blob = await api.userAvatar(profile.public_id);
    if (stale()) {
      return;
    }
    nextFace = URL.createObjectURL(blob);
  }
  if (stale()) {
    if (nextFace) URL.revokeObjectURL(nextFace);
    return;
  }
  page.value = profile;
  posts.value = recommendations;
  displayName.value = profile.display_name;
  surname.value = profile.surname;
  username.value = profile.username;
  bio.value = profile.bio;
  visibility.value = nextVisibility;
  ownUrl = nextFace;
  ownFace.value = nextFace;
  const people = [...profile.friends, ...profile.mutual];
  await Promise.all(people.map((person) => loadFace(person, seq).catch(() => {})));
}

watch(canMap, (allowed) => {
  if (!allowed) showMap.value = false;
});

watch(posts, () => {
  if (chip.value === "all" || chip.value === "drafts") return;
  const stillPublished = posts.value.some((post) => post.category === chip.value && post.status !== "draft");
  if (!stillPublished) chip.value = "all";
});

watch(categoryPosts, (rows) => {
  if (!rows.length) return;
  const values = new Set(rows.map((post) => post.visibility));
  const only = values.size === 1 ? [...values][0] : "";
  if (["self", "friends", "close", "everyone"].includes(only)) categoryVisibility.value = only;
});

watch(
  () => [props.publicId, props.active],
  ([id, active], previous) => {
    if (!active) return;
    if (!previous || previous[0] !== id) {
      chip.value = "all";
      showMap.value = false;
      editing.value = false;
      showAllFriends.value = false;
    }
    load().catch((err) => {
      error.value = err.message;
    });
  },
  { immediate: true },
);

onBeforeUnmount(releaseFaces);

function chooseCategory(next) {
  chip.value = next;
  const rows = posts.value.filter((post) => post.category === next);
  const values = new Set(rows.map((post) => post.visibility));
  const only = values.size === 1 ? [...values][0] : "";
  categoryVisibility.value = ["self", "friends", "close", "everyone"].includes(only) ? only : "friends";
}

async function runCategory(body, confirmText) {
  if (confirmText && !window.confirm(confirmText)) return;
  error.value = "";
  categoryBusy.value = true;
  try {
    await api.manageCategory(chip.value, body);
    await load();
    emit("managed");
  } catch (err) {
    error.value = err.message;
  } finally {
    categoryBusy.value = false;
  }
}

async function onAvatar(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  error.value = "";
  try {
    const me = await api.uploadAvatar(file);
    emit("saved", me);
    await load();
  } catch (err) {
    error.value = err.message;
  }
}

async function save() {
  error.value = "";
  busy.value = true;
  try {
    const me = await api.updateMe({
      display_name: displayName.value.trim(),
      surname: surname.value.trim(),
      username: username.value.trim(),
      bio: bio.value,
      profile_visibility: visibility.value,
    });
    emit("saved", me);
    editing.value = false;
    await load();
  } catch (err) {
    error.value = err.message;
  } finally {
    busy.value = false;
  }
}

async function addFriend() {
  error.value = "";
  try {
    await api.sendFriendRequest(page.value.username);
    await load();
  } catch (err) {
    error.value = err.message;
  }
}

async function toggleClose() {
  error.value = "";
  try {
    await api.setCloseFriend(page.value.username, !page.value.is_close);
    await load();
  } catch (err) {
    error.value = err.message;
  }
}
</script>

<template>
  <section class="page profile-page">
    <button class="link" @click="emit('back')">Назад</button>
    <p v-if="error" class="error">{{ error }}</p>
    <template v-if="page && page.public_id === publicId">
      <header class="profile-head">
        <label v-if="page.is_self" class="face-button">
          <img v-if="ownFace" class="avatar profile-avatar" :src="ownFace" alt="Фото профиля" />
          <span v-else class="avatar-letter">{{ letter }}</span>
          <input class="file-hidden" type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" @change="onAvatar" />
        </label>
        <div v-else class="face-button">
          <img v-if="ownFace" class="avatar profile-avatar" :src="ownFace" alt="" />
          <span v-else class="avatar-letter">{{ letter }}</span>
        </div>
        <div class="profile-id">
          <h2>{{ fullName }}</h2>
          <p class="profile-tag">@{{ page.username }}</p>
          <p v-if="page.bio" class="profile-bio">{{ page.bio }}</p>
        </div>
      </header>
      <div class="profile-actions">
        <button v-if="page.is_self" class="link" @click="editing = !editing">{{ editing ? "Закрыть" : "Редактировать" }}</button>
        <button v-if="page.is_self" class="link" @click="emit('settings')">Настройки</button>
        <button v-if="page.relation === 'none'" class="primary" @click="addFriend">Добавить в друзья</button>
        <p v-if="page.relation === 'outgoing'" class="muted">Заявка отправлена</p>
        <p v-if="page.relation === 'incoming'" class="muted">Хочет добавить вас</p>
        <button v-if="page.relation === 'friend'" @click="toggleClose">
          {{ page.is_close ? "Убрать из близких" : "В близкие друзья" }}
        </button>
      </div>

      <form v-if="editing" class="stack" @submit.prevent="save">
        <label>Имя <input v-model="displayName" maxlength="100" required /></label>
        <label>Фамилия <input v-model="surname" maxlength="100" /></label>
        <label>Юзертег <input v-model="username" autocapitalize="none" maxlength="50" required /></label>
        <label>О себе <textarea v-model="bio" maxlength="500" rows="3"></textarea></label>
        <label>
          Кто видит описание и фото
          <select v-model="visibility">
            <option value="everyone">Все пользователи</option>
            <option value="friends">Только друзья</option>
          </select>
        </label>
        <button class="primary" :disabled="busy">Сохранить</button>
      </form>

      <p v-if="page.friend_count !== null" class="profile-stats">
        <span>{{ publishedCount }} рек.</span>
        <button class="link" @click="showAllFriends = true">{{ page.friend_count }} друзей</button>
      </p>

      <div v-if="shownFriends.length" class="friend-rail">
        <button
          v-for="person in shownFriends"
          :key="person.public_id"
          class="friend-chip"
          @click="emit('open-profile', person.public_id)"
        >
          <img v-if="faces[person.public_id]" class="avatar mini" :src="faces[person.public_id]" alt="" />
          <span v-else class="avatar-letter mini">{{ person.display_name.trim().charAt(0).toUpperCase() }}</span>
          <span>{{ person.display_name }}</span>
        </button>
      </div>
      <button v-if="page.friends.length > 6" class="link" @click="showAllFriends = !showAllFriends">
        {{ showAllFriends ? "Свернуть" : `Все ${page.friends.length}` }}
      </button>
      <div v-if="page.mutual_count" class="mutual">
        <p class="muted">{{ page.mutual_count }} общих</p>
        <div class="friend-rail">
          <button
            v-for="person in page.mutual"
            :key="person.public_id"
            class="friend-chip"
            @click="emit('open-profile', person.public_id)"
          >
            <img v-if="faces[person.public_id]" class="avatar mini" :src="faces[person.public_id]" alt="" />
            <span v-else class="avatar-letter mini">{{ person.display_name.trim().charAt(0).toUpperCase() }}</span>
            <span>{{ person.display_name }}</span>
          </button>
        </div>
      </div>

      <div class="section-head">
        <h2>Рекомендации</h2>
        <div v-if="canMap" class="chips view-switch">
          <button type="button" class="chip" :class="{ active: !showMap }" @click="showMap = false">Список</button>
          <button type="button" class="chip" :class="{ active: showMap }" @click="showMap = true">Карта</button>
        </div>
      </div>
      <div class="chips">
        <button type="button" class="chip" :class="{ active: chip === 'all' }" @click="chip = 'all'">Все</button>
        <button
          v-for="item in usedCategories"
          :key="item.id"
          type="button"
          class="chip"
          :class="{ active: chip === item.id }"
          @click="chooseCategory(item.id)"
        >
          {{ item.label }}
        </button>
        <button v-if="hasDrafts" type="button" class="chip" :class="{ active: chip === 'drafts' }" @click="chip = 'drafts'">
          Черновики
        </button>
      </div>
      <section v-if="page.is_self && categoryPosts.length" class="category-tools">
        <p class="muted">
          {{ categoryLabel(chip) }} · {{ categoryPosts.length }}
          <template v-if="categoryDraftCount">, из них черновиков {{ categoryDraftCount }}</template>
          <template v-if="categoryHidden"> · скрыто, видите только вы</template>
        </p>
        <p class="muted">Если постов в категории не останется, она пропадёт. Её снова можно поставить при правке поста.</p>
        <label>
          Кто видит
          <select v-model="categoryVisibility">
            <option value="self">Только я</option>
            <option value="friends">Друзья</option>
            <option value="close">Близкие друзья</option>
            <option value="everyone">Все</option>
          </select>
        </label>
        <div class="actions">
          <button type="button" :disabled="categoryBusy" @click="runCategory({ action: 'visibility', visibility: categoryVisibility })">
            Применить ко всем
          </button>
          <button type="button" :disabled="categoryBusy || categoryHidden" @click="runCategory({ action: 'visibility', visibility: 'self' })">
            Скрыть
          </button>
          <button
            type="button"
            :disabled="categoryBusy"
            @click="runCategory({ action: 'clear' }, `Убрать категорию «${categoryLabel(chip)}»? Посты останутся без категории.`)"
          >
            Убрать категорию
          </button>
          <button
            type="button"
            class="danger"
            :disabled="categoryBusy"
            @click="runCategory({ action: 'delete' }, `Удалить категорию «${categoryLabel(chip)}» вместе с ${categoryPosts.length} постами?`)"
          >
            Удалить с постами
          </button>
        </div>
      </section>
      <button v-if="page.is_self && chip === 'all' && !posts.length" class="empty-feed" @click="emit('add')">
        Рекомендаций нет, но вы можете добавить свою
      </button>
      <p v-else-if="chip === 'all' && !page.is_self && page.relation !== 'friend' && !posts.length" class="muted">
        Рекомендации видны друзьям.
      </p>
      <p v-else-if="chip === 'all' && !page.is_self && page.relation === 'friend' && !visiblePosts.length" class="muted">
        Рекомендаций пока нет.
      </p>
      <p v-else-if="chip !== 'all' && chip !== 'drafts' && !visiblePosts.length" class="muted">
        В этой категории пока нет рекомендаций.
      </p>
      <MapView
        v-if="showMap"
        :items="visiblePosts"
        :config="config"
        embedded
        fit
        @open="emit('open', $event)"
      />
      <template v-if="!showMap">
      <RecommendationCard
        v-for="item in visiblePosts"
        :key="item.id"
        :item="item"
        :lists="lists"
        :show-map-button="item.on_map"
        :show-list-button="item.on_map"
        @open="emit('open', item)"
        @edit="emit('edit', item)"
        @open-author="emit('open-profile', $event)"
        @to-list="emit('to-list', $event)"
        @show-on-map="emit('show-on-map', $event)"
      />
      </template>
    </template>
  </section>
</template>
