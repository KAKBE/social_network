# Квест 8. Фоновая обработка

| | |
|---|---|
| Проект | «По Следу» |
| Дата | 21.11.2026 |
| Участники | состав пары не передан |
| Код | https://github.com/KAKBE/social_network/commit/ee14534 |

Операция: публикация рекомендации ставит одно задание — создать уведомление каждому другу, которому она видна. Автор получает ответ сразу, друзья видят колокольчик после воркера. Одно задание — `notification_jobs.id`, попытки — `attempts`.

Публикация и строка задания коммитятся вместе → отдельный процесс берёт задание → пишет уведомления и `process_count`. Пока задание в работе, у него `status=claimed` и `lease_until`. После успеха: `status=done`, `process_count=1`. Отдельного статуса «провал» нет: истёкшая аренда снова делает задание свободным. Отказ опоздавшего воркера виден в его логе как `stale_owner`.

## Очередь

PostgreSQL, не RabbitMQ. Уведомление нельзя отправить о рекомендации, которой нет: задание пишется в той же транзакции, что и публикация. Брокера в проекте нет.

Захват — короткая транзакция, `claim_token` меняется каждый раз. Уведомления пишутся только после коммита захвата и только если аренда ещё наша:

```sql
UPDATE notification_jobs
SET status = 'claimed', claim_token = :token, claimed_by = :worker,
    attempts = attempts + 1,
    lease_until = now() + make_interval(secs => :lease)
WHERE id = :id
```

```python
owns = session.scalar(
    select(NotificationJob.id).where(
        NotificationJob.id == job_id,
        NotificationJob.claim_token == claim_token,
        NotificationJob.status == "claimed",
        NotificationJob.lease_until > func.now(),
    )
)
```

Если владелец не совпал, транзакция отменяется и уведомления не пишутся. Повтор одной рекомендации не создаёт вторую строку: уникальность `(user_id, recommendation_id)`. `process_count` растёт только в успешном завершении.

Воркер — отдельный процесс: `python -m app.worker`. Черновик задание не ставит. Будущая публикация ждёт `available_at`.

Команды из `backend` (провал-проверки — тестовая база, обычный прогон ниже — рабочая):

```powershell
$env:DATABASE_URL="postgresql+psycopg://posledu:posledu@localhost:5432/posledu_test"
$env:NOTIFY_LEASE_SECONDS="1"
..\.venv\Scripts\python -m pytest tests/test_notifications.py
$env:DATABASE_URL="postgresql+psycopg://posledu:posledu@localhost:5432/posledu"
..\.venv\Scripts\python -m app.worker --once
..\.venv\Scripts\python -m app.worker --status 1
```

Обычный прогон, рабочая база, рекомендация 84, тот же `job_id=1`:

```text
job_id=1 event=claim claim_token=34c14f27-8b59-483a-babd-6757c81bf96e worker=browser attempt=1
job_id=1 event=done process_count=1 notifications=6
{"job_id": 1, "recommendation_id": 84, "status": "done", "claim_token": "34c14f27-8b59-483a-babd-6757c81bf96e", "claimed_by": "browser", "attempts": 1, "process_count": 1, "notifications": 6}
```

Шесть уведомлений — пять друзей из наполнения и `checkuser`. Автор и посторонние — 0. Аня открыла «Квест 8» через колокольчик, счётчик исчез. У Саши, Кристины, Димы, Маши и `checkuser` оно ещё непрочитано.

## Две проверки сбоя

Оба раза на тестовой базе, `NOTIFY_LEASE_SECONDS=1`, новые рекомендации. Лог `pytest tests/test_notifications.py -s`.

**1. Обрыв после захвата.** Ожидание: процесс выходит сразу после claim, после аренды тот же `job_id` берётся снова и завершается без новой постановки.

```text
job_id=5 event=claim claim_token=f34ef9f6-13ba-4030-b8ff-b3a28164faa3 worker=crash attempt=1
job_id=5 event=crash-after-claim
job_id=5 event=claim claim_token=c09162e0-a0fe-467b-9502-0babf68b37e7 worker=recover attempt=2
job_id=5 event=done process_count=1 notifications=5
```

Факт: `job_id` тот же, токен другой, `attempts=2`, `process_count=1`, уведомлений 5.

**2. Опоздавший владелец.** Ожидание: первый воркер ждёт дольше аренды, второй завершает задание, первый при записи получает отказ и не меняет результат.

```text
job_id=6 event=claim claim_token=e5c5c6f6-ed8c-44dd-b5f9-74836f627f67 worker=holder attempt=1
job_id=6 event=hold seconds=3.0
job_id=6 event=claim claim_token=d90c9356-214a-4997-a18f-55b07fb547a4 worker=finisher attempt=2
job_id=6 event=done process_count=1 notifications=5
job_id=6 event=stale_owner claim_token=e5c5c6f6-ed8c-44dd-b5f9-74836f627f67
{"job_id": 6, "status": "done", "attempts": 2, "process_count": 1, "notifications": 5}
```

Факт: код выхода первого воркера — 2. Его токен в `stale_owner` не совпадает с токеном, которым задание завершено. `process_count` остался 1, строк уведомлений 5.

## Граница согласованности

Рекомендация и задание сохраняются одним `commit` (`enqueue` вызывается до него и в создании, и в публикации черновика). Откат этой транзакции убирает обе строки: тест добавил рекомендацию, вызвал `enqueue` и сделал `rollback` — задания не осталось. Постановка после уже закоммиченной публикации не используется.
