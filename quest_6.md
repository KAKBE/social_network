# Квест 6. Репозиторий прототипа «По Следу»

Участники команды: Яшин Даниил, Веретнов Александр, Кателкин Никита (Последам-1-12.pdf, слайд 11).

## Действие

Авторизованный пользователь Лёша открывает карту и видит места, которые рекомендовали его друзья. Нажатие на метку показывает название места, имя автора и текст рекомендации.

Друзей и места в этом сценарии пользователь не создаёт: их записывает `backend/app/seed.py`. Регистрации и добавления друга в приложении нет. Экран регистрации есть только на макете `docs/mockups/макет_1.png`.

## Путь по файлам

1. `frontend/index.html` отдаёт страницу и подключает `frontend/src/main.js`. `main.js` монтирует Vue-приложение `frontend/src/App.vue` в `#app`.
2. Пока в `localStorage` нет ключа `posledu.token`, `App.vue` показывает `frontend/src/components/LoginView.vue`. Форма отправляет логин и пароль в `api.login` (`frontend/src/api.js`): `POST /api/auth/login` с телом `{ "username", "password" }`.
3. `backend/app/main.py` передаёт запрос маршрутам из `backend/app/api.py`. `login` ищет строку в таблице `users`, проверяет пароль (`backend/app/security.py`) и записывает токен в таблицу `auth_sessions`. Ответ: `{ "token" }`.
4. `LoginView.vue` передаёт токен в `App.vue`. `api.js` сохраняет его в `localStorage` и дальше шлёт заголовок `Authorization: Bearer <token>`.
5. `App.vue` параллельно вызывает четыре запроса: `GET /api/config`, `GET /api/me`, `GET /api/feed?limit=100`, `GET /api/lists`.
6. `current_user` в `api.py` по токену читает `auth_sessions` и `users`. Без токена или с неизвестным токеном ответ `401` и текст «Нужен вход» или «Сессия не найдена».
7. `GET /api/feed` выбирает из `recommendations` строки, у которых `author_id` равен пользователю или входит в `friendships.friend_id` для этого пользователя. Вместе с рекомендацией загружаются `users` (автор) и `places` (место). Ответ — список объектов: `id`, `text`, `created_at`, `author` (`id`, `username`, `display_name`), `place` (`id`, `name`, `address`, `lat`, `lon`), `is_own`.
8. `App.vue` кладёт этот список в `feed` и передаёт его в `frontend/src/components/MapView.vue`.
9. `GET /api/config` возвращает `tile_url` и `tile_attribution` из `backend/app/config.py`. По умолчанию `tile_url` — `https://tile.openstreetmap.org/{z}/{x}/{y}.png`. `MapView.vue` создаёт карту Leaflet и запрашивает фрагменты подложки по этому адресу из браузера. Координаты меток берутся из `place.lat` и `place.lon` ответа ленты, а не из подложки.
10. Нажатие на метку возвращает выбранный элемент ленты в `App.vue`. `frontend/src/components/RecommendationCard.vue` показывает `place.name`, «Рекомендует » и `author.display_name`, дату `created_at` и `text`.

Хранилище — PostgreSQL, таблицы описаны в `backend/app/models.py`: `users`, `auth_sessions`, `friendships`, `places`, `recommendations`. Подключение по умолчанию задано в `backend/app/config.py`: база `posledu` на `localhost:5432`. Контейнер — `docker-compose.yml`, образ `postgres:16-alpine`.

На диаграмме C4 уровня Container (Diagrams.pdf, стр. 2) к картографическому провайдеру обращается Backend API. В коде фрагменты подложки запрашивает браузер, `MapView.vue`. Лента, вход и места идут через Backend API.

## Что работает в этом сценарии

Работает путь от формы входа до метки и карточки, если в базе есть пользователи, дружба и рекомендации.

`backend/app/seed.py` создаёт пользователя `lesha` (отображаемое имя «Лёша»), друзей `anya`, `sasha`, `kristina`, `dima`, `masha` и посторонних `stranger1`, `stranger2`, `stranger3`. Пароль всех этих пользователей — `demo1234`. Дружба с Лёшей записывается только для пяти друзей. У каждого друга и каждого постороннего создаётся 10 рекомендаций. Названия мест — «Тестовое место №N» с категорией из списка в `seed.py`, адрес — «синтетические тестовые данные». У Лёши своих рекомендаций скрипт не создаёт.

Посторонние в ответ `GET /api/feed` для Лёши не попадают: их нет в `friendships` Лёши, а фильтр ленты другой связи не смотрит. Тот же фильтр проверяет `backend/tests/test_access.py`.

Добавить друга через интерфейс нельзя: в `api.py` есть только `GET /api/friends`. Зарегистрироваться нельзя: обработчика регистрации нет.

## Два решения

### Один Backend API и фильтр «я и мои друзья» в одном месте

Задача сценария: на карте только места друзей и свои.

Видно в `backend/app/api.py`: `friend_ids_subquery` и условие `feed`. Записи дружбы лежат в PostgreSQL, таблица `friendships` (`backend/app/models.py`).

Другой вариант записан в `docs/06_ADR.md`, ADR-1: отдельные службы для пользователей, ленты и мест. Для этого сценария выбран один процесс FastAPI: и лента, и проверка видимости читают одну таблицу `friendships`.

### Подложка карты из браузера, места друзей — из своей базы

Задача сценария: показать метки друзей на карте.

Список мест приходит из `GET /api/feed` и таблиц `recommendations` и `places`. Адрес подложки приходит из `GET /api/config` (`backend/app/config.py`). Рисует метки и запрашивает подложку `frontend/src/components/MapView.vue`.

Другой вариант записан в `docs/06_ADR.md`, ADR-3: Backend API сам скачивает фрагменты карты и отдаёт их клиенту, как нарисовано на C4. В образце фрагменты запрашивает браузер по `tile_url`. Меняется адрес в переменной `TILE_URL`, без правки `MapView.vue`.

## Как повторить проверку

Нужны Docker, Python с зависимостями из `backend/requirements.txt` и Node.js для сборки интерфейса.

```powershell
cd C:\Users\User\Desktop\Code\social_network
docker compose up -d db
cd frontend
npm install
npm run build
cd ..\backend
..\.venv\Scripts\python -m pip install -r requirements.txt
..\.venv\Scripts\python -m app.seed
..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`python -m app.seed` заново заполняет пользователей, дружбу, места и рекомендации. Таблицы `perf_samples` и `geocode_cache` этот запуск не очищает.

Открыть `http://127.0.0.1:8000`. Ввести логин `lesha` и пароль `demo1234`. На вкладке «Карта» нажать любую метку. На карточке должны быть название вида «Тестовое место №…», строка «Рекомендует » с именем Аня, Саша, Кристина, Дима или Маша и один из текстов из списка `TEXTS` в `backend/app/seed.py`.

Тот же вход и ленту можно увидеть запросами:

```powershell
$login = Invoke-RestMethod http://127.0.0.1:8000/api/auth/login -Method Post -ContentType "application/json" -Body '{"username":"lesha","password":"demo1234"}'
$feed = Invoke-RestMethod "http://127.0.0.1:8000/api/feed?limit=100" -Headers @{ Authorization = "Bearer $($login.token)" }
$feed[0].author.display_name
$feed[0].place.name
$feed[0].text
```

В режиме разработки интерфейс запускается отдельно: `npm run dev` в каталоге `frontend`. Запросы `/api` проксируются на `http://localhost:8000` (`frontend/vite.config.js`). Backend при этом тоже должен быть запущен.
