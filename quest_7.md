# Квест 7. Миграции и резервные копии

| | |
|---|---|
| Проект | «По Следу» |
| Дата | 14.11.2026 |
| Участники (очно) | Яшин Даниил, Веретнов Александр, Кателкин Никита |
| Репозиторий | https://github.com/KAKBE/social_network |

## 1. Политика миграций

### 1.1 Инструмент

- Инструмент — **Alembic 1.20.1** (`backend/requirements.txt`), работает с моделями SQLAlchemy из `backend/app/models.py`.
- Настройки: `backend/alembic.ini`, окружение: `backend/migrations/env.py`. Адрес базы в файлах не хранится — берётся из переменной `DATABASE_URL` через `app.config.settings`.
- Файлы миграций: `backend/migrations/versions/`.
- Имя файла: `<дата YYYYMMDD>_<номер ревизии из 4 цифр>_<описание>.py`. Номер ревизии задаётся явно (`--rev-id`) и растёт на 1; порядок применения определяется полем `down_revision` в файле (цепочка без ветвлений).

| Файл | Ревизия | Предыдущая | Что делает |
|---|---|---|---|
| `20261114_0001_initial_schema.py` | 0001 | — | 9 таблиц образца и индекс `ix_recommendations_author_created` |
| `20261114_0002_places_point_corrected.py` | 0002 | 0001 | столбец `places.point_corrected boolean NOT NULL DEFAULT false` |

### 1.2 Команды

Все команды — из каталога `backend`, база берётся из `DATABASE_URL`.

| Действие | Команда |
|---|---|
| Создать миграцию по изменённым моделям | `..\.venv\Scripts\alembic revision --autogenerate --rev-id 0003 -m "описание"` |
| Создать пустую миграцию (ручной SQL, перенос данных) | `..\.venv\Scripts\alembic revision --rev-id 0003 -m "описание"` |
| Просмотреть цепочку | `..\.venv\Scripts\alembic history` |
| Просмотреть SQL без применения | `..\.venv\Scripts\alembic upgrade 0002:0003 --sql` |
| Текущая версия базы | `..\.venv\Scripts\alembic current` |
| Есть ли расхождение моделей и схемы | `..\.venv\Scripts\alembic check` |
| Применить все новые | `..\.venv\Scripts\alembic upgrade head` |
| Откатить последнюю | `..\.venv\Scripts\alembic downgrade -1` |
| Пометить базу, созданную без миграций (один раз) | `..\.venv\Scripts\alembic stamp 0001` |

### 1.3 Таблица учёта

Alembic хранит версию схемы в таблице `alembic_version` с одним столбцом `version_num varchar(32)` (первичный ключ). В ней одна строка — номер последней применённой ревизии. При `upgrade` Alembic обновляет строку в той же транзакции, что и изменение схемы (PostgreSQL поддерживает транзакционный DDL; видно в SQL ниже).

Пример из локальной базы после перевода на миграции:

```
#~ SELECT * FROM alembic_version;
 version_num
-------------
 0002
(1 row)
```

### 1.4 Порядок запуска

- Миграцию создаёт и первым применяет участник, который меняет модели, — на своей локальной базе, затем на тестовой (`pytest` применяет миграции сам).
- На общей базе (будущий сервер) миграции запускает тот, кто выкладывает версию, отдельным шагом **до** запуска приложения и **после** резервной копии.
- Порядок запуска:
  1. база: `docker compose up -d db` (ждём состояния `healthy`);
  2. резервная копия: `powershell -ExecutionPolicy Bypass -File scripts\backup.ps1` (если есть новые миграции);
  3. миграции: `cd backend; ..\.venv\Scripts\alembic upgrade head`;
  4. приложение: `..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.
- Приложение само схему не меняет. При старте `app/migrations.py: assert_schema_current()` сравнивает версию в `alembic_version` с последней ревизией и останавливает запуск, если они не совпадают (проверено, раздел 4.2).
- `python -m app.seed` (тестовые данные) сначала выполняет `upgrade head`, затем очищает пользовательские таблицы (`TRUNCATE ... RESTART IDENTITY CASCADE`) и заполняет заново; `perf_samples` и `geocode_cache` не очищаются.

### 1.5 Проверка новой миграции, ошибки, откат

Перед коммитом новой миграции:

1. Прочитать сгенерированный файл: автогенерация не видит переименований (делает удаление + добавление) и не переносит данные.
2. `alembic upgrade <пред>:<новая> --sql` — проверить SQL глазами.
3. Создать пустую базу, `alembic upgrade head` — схема строится с нуля.
4. На копии с данными: `alembic upgrade head`, затем `alembic check` → «No new upgrade operations detected.», затем выборка известных записей.
5. Повторный `alembic upgrade head` ничего не применяет.
6. `pytest` (тестовая база `posledu_test` мигрирует автоматически).

Если миграция упала:

- Миграция идёт в одной транзакции: при ошибке PostgreSQL откатывает изменения, `alembic_version` остаётся на прежней ревизии. Проверить: `alembic current`.
- Приложение со старой версией схемы не запустится (проверка при старте) — это ожидаемо.
- Исправить: если миграция ещё не применена ни на одной общей базе — исправить файл; если уже применена где-либо — новая миграция с исправлением.
- Если данные повреждены — восстановить из копии, снятой перед миграцией (раздел 3.5).

Ограничения отката:

- `downgrade` возвращает схему, но не данные: удалённый столбец или таблица теряют значения. Проверено: значение `point_corrected = true` после `downgrade -1` и `upgrade head` стало `false` (раздел 4.1, шаг 6).
- Поэтому откат через `downgrade` допустим только на локальной и тестовой базе; на общей базе при потере данных — восстановление из копии.

## 2. Политика резервного копирования

### 2.1 Что копируется и согласованность

- Копируется вся база `posledu`: пользователи, дружба, места, рекомендации, списки, сессии входа, замеры RAT (`perf_samples`), кэш геокодера (`geocode_cache`) и `alembic_version` — то есть копия знает свою версию схемы.
- Пользовательских файлов в образце нет: API не принимает загрузку файлов, фото не хранятся. Копировать, кроме базы, нечего.
- Согласованность: `pg_dump` читает всю базу в одной транзакции (один снимок), поэтому таблицы в копии согласованы между собой без остановки приложения. Формат — custom (`-Fc`), восстанавливается через `pg_restore`.
- После снятия копия проверяется командой `pg_restore --list`; нечитаемая копия не сохраняется, в журнал пишется `ERROR`.

### 2.2 RPO и RTO

| Показатель | Значение | Обоснование |
|---|---|---|
| RPO (сколько данных можно потерять) | 24 часа; для изменения схемы — 0 (копия непосредственно перед миграцией) | данные образца — тестовые пользователи и места, заново создаются `python -m app.seed`; новые записи появляются только при показах и испытаниях; самое ценное — замеры RAT — пишутся только во время испытаний, перед которыми снимается копия |
| RTO (за сколько восстановиться) | 30 минут | восстановление копии текущего объёма (24 816 байт) в новую базу заняло 2,2 с (раздел 4.3); остальное время — найти копию, сравнить записи, переключить `DATABASE_URL`, перезапустить приложение |

### 2.3 Частота, отдельное хранение, доступ, уведомления

| Вопрос | Решение | Состояние |
|---|---|---|
| Частота | ежедневно в 03:00 и вручную перед каждой миграцией и испытанием | вручную — проверено; расписание подготовлено (команда ниже) |
| Где хранятся | `backups/` в корне проекта (не в Docker-томе `pgdata`, где лежит база) | проверено |
| Отдельно от исходного сервера | второй экземпляр через `backup.ps1 -CopyTo <папка>` на другой диск или в облачную папку | механизм проверен на локальной папке; место не выбрано |
| Кто имеет доступ | только участники команды: в копии есть хэши паролей и действующие токены сессий (`auth_sessions`) | `backups/`, `*.dump`, `dump-*.sql` в `.gitignore`; проверено `git check-ignore` |
| Уведомление об ошибке | скрипт пишет `ERROR` в `backups/backup.log` и завершается с кодом 1; в Планировщике задач это видно как код последнего запуска | журнал и код возврата — проверено; отправка уведомления — не настроена |

Расписание (подготовлено, не зарегистрировано):

```powershell
schtasks /Create /TN "posledu-backup" /SC DAILY /ST 03:00 /TR "powershell -ExecutionPolicy Bypass -File C:\Users\User\Desktop\Code\social_network\scripts\backup.ps1"
schtasks /Create /TN "posledu-prune" /SC DAILY /ST 03:30 /TR "powershell -ExecutionPolicy Bypass -File C:\Users\User\Desktop\Code\social_network\scripts\prune_backups.ps1"
```

### 2.4 Срок хранения

- Храним 7 последних копий (`prune_backups.ps1 -Keep 7`): при ежедневном запуске это неделя.
- Порядок копий — по дате и времени в имени файла `posledu_yyyyMMdd-HHmmss.dump`.
- Свежая копия не удаляется никогда: `-Keep` не меньше 1, а перед удалением самая новая копия проверяется `pg_restore --list`; если она нечитаема, скрипт ничего не удаляет и завершается с кодом 1 (проверено, раздел 4.4).
- Перед удалением можно посмотреть список (`-DryRun`).

### 2.5 Команды

Из корня проекта:

| Действие | Команда |
|---|---|
| Резервная копия | `powershell -ExecutionPolicy Bypass -File scripts\backup.ps1` |
| Копия с вторым экземпляром | `powershell -ExecutionPolicy Bypass -File scripts\backup.ps1 -CopyTo D:\posledu-backups` |
| Восстановление в новую пустую базу | `powershell -ExecutionPolicy Bypass -File scripts\restore.ps1 -File backups\posledu_20261114-130736.dump -Target posledu_restore` |
| Список удаляемых копий | `powershell -ExecutionPolicy Bypass -File scripts\prune_backups.ps1 -Keep 7 -DryRun` |
| Удаление старых копий | `powershell -ExecutionPolicy Bypass -File scripts\prune_backups.ps1 -Keep 7` |

`restore.ps1` отказывается работать, если база-цель уже существует: восстановление всегда идёт в новую пустую базу. После сравнения записей приложение переключается на неё через `DATABASE_URL`.

### 2.6 Проверка восстановления

- Восстановление проверяет участник, который не снимал копию, — раз в две недели и после каждой миграции.
- Порядок: `restore.ps1` в новую базу → сравнение числа строк и контрольных сумм таблиц с исходной (запрос из раздела 4.3) → вход под `lesha` и лента на восстановленной базе → удаление проверочной базы.

## 3. Проверки на данных проекта

Окружение: Windows, PowerShell 5.1, Docker, контейнер `social_network-db-1` (`PostgreSQL 16.15`).

### 3.1 Миграции на пустой базе

Шаг 1. Пустая база и первая миграция:

```powershell
docker compose exec -T db psql -U posledu -d posledu -c "CREATE DATABASE posledu_q7 OWNER posledu"
cd backend
$env:DATABASE_URL = "postgresql+psycopg://posledu:posledu@localhost:5432/posledu_q7"
..\.venv\Scripts\alembic upgrade 0001
..\.venv\Scripts\alembic current
docker compose exec -T db psql -U posledu -d posledu_q7 -c "\dt"
```

```
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, initial schema
0001 (head)
 public | alembic_version  | table | posledu
 public | auth_sessions    | table | posledu
 public | friendships      | table | posledu
 public | geocode_cache    | table | posledu
 public | perf_samples     | table | posledu
 public | place_list_items | table | posledu
 public | place_lists      | table | posledu
 public | places           | table | posledu
 public | recommendations  | table | posledu
 public | users            | table | posledu
(10 rows)
```

Шаг 2. Записи на схеме 0001:

```sql
INSERT INTO users (username, display_name, password_hash) VALUES ('anya', 'Аня', 'x'), ('lesha', 'Лёша', 'x');
INSERT INTO places (name, address, lat, lon, created_by) VALUES ('Тестовое место №1', 'Москва, Тверская ул., 1', 55.757, 37.613, 1), ('Тестовое место №2', '', 55.760, 37.620, 1);
INSERT INTO recommendations (author_id, place_id, text, created_at) VALUES (1, 1, 'Тихо, есть розетки', '2026-11-14 10:00+03'), (1, 2, 'Хороший кофе', '2026-11-14 10:05+03');
```

```
INSERT 0 2
INSERT 0 2
INSERT 0 2
```

Шаг 3. Отдельная миграция с новым полем — создана по изменённой модели:

```powershell
..\.venv\Scripts\alembic revision --autogenerate --rev-id 0002 -m "places point_corrected"
```

```
INFO  [alembic.autogenerate.compare.tables] Detected added column 'places.point_corrected'
Generating ...\backend\migrations\versions\20261114_0002_places_point_corrected.py ...  done
```

Шаг 4. SQL до применения, применение, схема, данные, таблица учёта:

```powershell
..\.venv\Scripts\alembic upgrade 0001:0002 --sql
..\.venv\Scripts\alembic history
..\.venv\Scripts\alembic upgrade head
..\.venv\Scripts\alembic current
docker compose exec -T db psql -U posledu -d posledu_q7 -c "\d places" -c "SELECT id, name, created_by, point_corrected FROM places ORDER BY id" -c "SELECT r.id, u.username, p.name, r.text FROM recommendations r JOIN users u ON u.id = r.author_id JOIN places p ON p.id = r.place_id ORDER BY r.id" -c "SELECT * FROM alembic_version"
```

```
BEGIN;
-- Running upgrade 0001 -> 0002
ALTER TABLE places ADD COLUMN point_corrected BOOLEAN DEFAULT false NOT NULL;
UPDATE alembic_version SET version_num='0002' WHERE alembic_version.version_num = '0001';
COMMIT;

0001 -> 0002 (head), places point_corrected
<base> -> 0001, initial schema

INFO  [alembic.runtime.migration] Running upgrade 0001 -> 0002, places point_corrected
0002 (head)

     Column      |          Type          | Collation | Nullable |              Default
-----------------+------------------------+-----------+----------+------------------------------------
 id              | integer                |           | not null | nextval('places_id_seq'::regclass)
 name            | character varying(200) |           | not null |
 address         | character varying(300) |           | not null |
 lat             | double precision       |           | not null |
 lon             | double precision       |           | not null |
 created_by      | integer                |           | not null |
 point_corrected | boolean                |           | not null | false

 id |       name        | created_by | point_corrected
----+-------------------+------------+-----------------
  1 | Тестовое место №1 |          1 | f
  2 | Тестовое место №2 |          1 | f

 id | username |       name        |        text
----+----------+-------------------+--------------------
  1 | anya     | Тестовое место №1 | Тихо, есть розетки
  2 | anya     | Тестовое место №2 | Хороший кофе

 version_num
-------------
 0002
```

Шаг 5. Повторный запуск и сверка моделей со схемой:

```powershell
..\.venv\Scripts\alembic upgrade head
..\.venv\Scripts\alembic check
docker compose exec -T db psql -U posledu -d posledu_q7 -tAc "SELECT count(*) FROM alembic_version"
```

```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
No new upgrade operations detected.
1
```

Повторный `upgrade head` не вывел ни одной строки `Running upgrade` — миграции не применялись повторно; в таблице учёта одна строка.

Шаг 6. Ограничение отката:

```powershell
docker compose exec -T db psql -U posledu -d posledu_q7 -c "UPDATE places SET point_corrected = true WHERE id = 2"
..\.venv\Scripts\alembic downgrade -1
..\.venv\Scripts\alembic upgrade head
docker compose exec -T db psql -U posledu -d posledu_q7 -c "SELECT id, point_corrected FROM places ORDER BY id"
```

```
UPDATE 1
INFO  [alembic.runtime.migration] Running downgrade 0002 -> 0001, places point_corrected
INFO  [alembic.runtime.migration] Running upgrade 0001 -> 0002, places point_corrected
 id | point_corrected
----+-----------------
  1 | f
  2 | f
```

Значение `true` у места 2 потеряно: откат удаляет данные столбца.

### 3.2 Перевод рабочей локальной базы на миграции

База `posledu` была создана `create_all` до появления миграций, таблицы `alembic_version` в ней не было.

Приложение с новой проверкой при старте на этой базе:

```powershell
cd backend
..\.venv\Scripts\python -c "import app.main"
```

```
RuntimeError: Database schema is at revision None, expected 0002. Run `alembic upgrade head` in backend/ before starting the app.
```

Данные до перевода:

```
users=9 places=81 recommendations=81 perf_samples=21 geocode_cache=1
```

Резервная копия перед переводом:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\backup.ps1
```

```
2026-11-14 13:06:49 OK posledu_20261114-130647.dump 23890 bytes
elapsed 1,7 s
```

Схема `posledu` сравнена со схемой, которую строит миграция 0001 на пустой базе `posledu_cmp`:

```powershell
docker compose exec -T db sh -c "pg_dump -U posledu -d posledu --schema-only -T alembic_version > /tmp/a.sql; pg_dump -U posledu -d posledu_cmp --schema-only -T alembic_version > /tmp/b.sql; diff /tmp/a.sql /tmp/b.sql"
```

Различаются только служебные строки `\restrict <случайный ключ>`, которые `pg_dump` 16.15 пишет в каждый дамп; таблицы, столбцы, ключи и индексы совпадают.

Пометка и применение 0002:

```powershell
..\.venv\Scripts\alembic stamp 0001
..\.venv\Scripts\alembic upgrade head
..\.venv\Scripts\alembic current
..\.venv\Scripts\alembic check
..\.venv\Scripts\python -c "import app.main; print('app import ok')"
```

```
INFO  [alembic.runtime.migration] Running stamp_revision  -> 0001
INFO  [alembic.runtime.migration] Running upgrade 0001 -> 0002, places point_corrected
0002 (head)
No new upgrade operations detected.
users=9 places=81 recommendations=81 perf_samples=21 geocode_cache=1 point_corrected_true=0
app import ok
```

### 3.3 Резервная копия и восстановление в отдельную пустую базу

```powershell
powershell -ExecutionPolicy Bypass -File scripts\backup.ps1
powershell -ExecutionPolicy Bypass -File scripts\restore.ps1 -File backups\posledu_20261114-130736.dump -Target posledu_restore
```

```
2026-11-14 13:07:37 OK posledu_20261114-130736.dump 24816 bytes
Restored posledu_20261114-130736.dump into posledu_restore
```

Время восстановления — 2,2 с (`Measure-Command`).

Сравнение всех таблиц: число строк и `md5` от всех строк таблицы, упорядоченных по тексту строки. Запрос выполнен на `posledu` и `posledu_restore`, результаты сравнены `Compare-Object`:

```sql
SELECT 'users' t, count(*) n, md5(string_agg(x::text, '|' ORDER BY x::text)) FROM users x UNION ALL
SELECT 'friendships', count(*), md5(string_agg(x::text, '|' ORDER BY x::text)) FROM friendships x UNION ALL
-- ... так же для places, recommendations, place_lists, place_list_items,
--     auth_sessions, perf_samples, geocode_cache, alembic_version
```

```
users|9|133c5cef311b900bb1511916e1259aca
friendships|22|9fbc0026640eefbfefe5ae6ecc974440
places|81|e18e71e00782b56969c16b4e2707d837
recommendations|81|527eb732dfda24ebbd2e5e183cc64af7
place_lists|1|3948e9262a3b721f9997f5d330448ea9
place_list_items|1|27ef9b4ddaee576ff5021206508ca225
auth_sessions|6|7422a593e66f42eed247649d32c0c440
perf_samples|21|cfc4ac14e282eb42247b9b9488e833e9
geocode_cache|1|ae95304aa9faa4b1c75fc0f5c9e5e9d6
alembic_version|1|a4310bbe1908ffaaf876d2c88cb0bfa7
--- compare
identical
```

Известные записи — одинаковы в обеих базах:

```
 username | display_name | friends
----------+--------------+---------
 lesha    | Лёша         |       5

 id | username |             name              |        lat         |        lon
----+----------+-------------------------------+--------------------+--------------------
  1 | anya     | Тестовое место №1 (коворкинг) |          55.702501 |          37.555006
 81 | lesha    | Спар                          | 55.797336953921516 | 37.402491688662856

 title | count
-------+-------
 Учёба |     1

 version_num
-------------
 0002
```

Приложение на восстановленной базе (вход `lesha`, лента):

```powershell
$env:DATABASE_URL = "postgresql+psycopg://posledu:posledu@localhost:5432/posledu_restore"
..\.venv\Scripts\python -c "from fastapi.testclient import TestClient; from app.main import app; c = TestClient(app); t = c.post('/api/auth/login', json={'username': 'lesha', 'password': 'demo1234'}).json()['token']; r = c.get('/api/feed?limit=100', headers={'Authorization': 'Bearer ' + t}); print('feed status', r.status_code, 'items', len(r.json()))"
```

```
feed status 200 items 51
```

Ошибка копирования (несуществующая база):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\backup.ps1 -Database no_such_db
```

```
pg_dump: error: connection to server on socket "/var/run/postgresql/.s.PGSQL.5432" failed: FATAL:  database "no_such_db" does not exist
2026-11-14 13:08:44 ERROR no_such_db_20261114-130843.dump pg_dump failed with exit code 1
exit=1
```

Второй экземпляр копии:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\backup.ps1 -CopyTo $env:TEMP\posledu_offsite_test
```

```
2026-11-14 13:10:31 OK posledu_20261114-131029.dump 24816 bytes
2026-11-14 13:10:31 OK posledu_20261114-131029.dump copied to C:\Users\User\AppData\Local\Temp\posledu_offsite_test
```

Проверочные базы `posledu_q7`, `posledu_restore`, `posledu_cmp` после проверок удалены (`DROP DATABASE`).

### 3.4 Очистка на тестовых копиях

В `backups\prune_test` создано 10 копий настоящего дампа с датами в имени с 05.11 по 14.11.2026:

```powershell
5..14 | % { Copy-Item $src ("backups\prune_test\posledu_202611{0:D2}-030000.dump" -f $_) }
powershell -ExecutionPolicy Bypass -File scripts\prune_backups.ps1 -BackupDir backups\prune_test -Keep 7 -DryRun
```

```
before: 10 files
Newest (checked): posledu_20261114-030000.dump
Keep (7): posledu_20261114-030000.dump, posledu_20261113-030000.dump, posledu_20261112-030000.dump, posledu_20261111-030000.dump, posledu_20261110-030000.dump, posledu_20261109-030000.dump, posledu_20261108-030000.dump
Delete (3): posledu_20261107-030000.dump, posledu_20261106-030000.dump, posledu_20261105-030000.dump
Dry run: nothing deleted
files after dry run: 10
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\prune_backups.ps1 -BackupDir backups\prune_test -Keep 7
```

```
Deleted 3 file(s)
=== remaining
posledu_20261108-030000.dump
posledu_20261109-030000.dump
posledu_20261110-030000.dump
posledu_20261111-030000.dump
posledu_20261112-030000.dump
posledu_20261113-030000.dump
posledu_20261114-030000.dump
```

Свежая копия `posledu_20261114-030000.dump` осталась. Защита от нечитаемой свежей копии:

```powershell
Set-Content backups\prune_test\posledu_20261115-030000.dump "not a dump" -Encoding ASCII
powershell -ExecutionPolicy Bypass -File scripts\prune_backups.ps1 -BackupDir backups\prune_test -Keep 3
```

```
pg_restore: error: input file does not appear to be a valid archive (too short?)
Newest backup posledu_20261115-030000.dump is not readable; nothing deleted
exit=1
files: 8
```

### 3.5 Автотесты и сборка

```powershell
docker compose exec -T db psql -U posledu -d posledu -c "DROP DATABASE posledu_test" -c "CREATE DATABASE posledu_test OWNER posledu"
cd backend; ..\.venv\Scripts\python -m pytest -q
docker compose exec -T db psql -U posledu -d posledu_test -tAc "SELECT version_num FROM alembic_version"
cd ..\frontend; npm run build
```

```
7 passed, 1 warning in 2.36s
0002
✓ built in 177ms
```

Тестовая база создана пустой и построена миграциями (`tests/conftest.py` вызывает `upgrade_to_head()`). Новый тест `tests/test_point_corrected.py` проверяет, что `point_corrected` сохраняется через API и по умолчанию равен `false`. Форма добавления в браузере с новым полем не проверялась.
