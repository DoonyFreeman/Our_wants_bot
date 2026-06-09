# our-wants-bot

Приватный Telegram-бот «общий вишлист на двоих». Пользуются ровно два человека
(владелец и его девушка). Каждый добавляет «хотелки» (места для прогулок, подарки,
3D-модели, куклы, планы и т.д.) с категорией и опциональными деталями. Партнёр
получает уведомление о новой записи и может просматривать списки по категориям,
открывать детали, редактировать и удалять записи.

> Документация и план проекта ведутся в Obsidian: `Claude Code/our-wants-bot/`
> (README, context, structure, daily-changes). Логируй изменения туда.

## Стек

- Python 3.12
- aiogram 3.x (long polling — webhook не нужен для 2 пользователей)
- SQLite + SQLAlchemy 2.0 (async, драйвер `aiosqlite`)
- Деплой: VPS, systemd-сервис, бэкап `wants.db` по cron
- Фото хранятся как Telegram `file_id` (файлы не скачиваем)

## Структура

```
Our_wants_bot/
├── bot.py              # entrypoint: Dispatcher, роутеры, middleware, polling
├── config.py           # env: BOT_TOKEN, ALLOWED_USER_IDS, имена пользователей
├── states.py           # FSM-состояния (AddItem, EditItem, NewCategory)
├── db/
│   ├── models.py       # SQLAlchemy: Category, Item
│   ├── database.py     # async engine, sessionmaker, init_db, seed категорий
│   └── repo.py         # CRUD-функции
├── handlers/
│   ├── start.py        # /start, главное меню
│   ├── add_item.py     # FSM добавления (категория→название→описание→ссылка→фото)
│   ├── view.py         # просмотр: категории → записи → карточка
│   ├── edit_item.py    # редактирование, удаление, смена статуса
│   └── categories.py   # пользовательские категории
├── keyboards/
│   ├── reply.py        # главное reply-меню
│   └── inline.py       # inline-клавиатуры
├── middlewares/
│   └── auth.py         # whitelist по ALLOWED_USER_IDS
├── services/
│   └── notify.py       # уведомления партнёру
├── deploy/
│   └── our-wants-bot.service
├── requirements.txt
├── .env.example
└── wants.db            # SQLite (в .gitignore)
```

## Модель данных

**categories**: `id`, `name`, `emoji`, `created_by` (NULL = встроенная, иначе telegram_id).
Встроенные seed-категории: 🚶 Место для прогулки, 🎁 Подарок на праздник,
🧩 3D-модель, 🪆 Кукла, ✨ Хотелка, 🗺 План.

**items**: `id`, `category_id` (FK), `author_id` (telegram_id), `title` (обязательное),
`description` (nullable), `url` (nullable), `photo_file_id` (nullable),
`status` (active/done), `created_at`, `updated_at`.

## Ключевые правила

- **Доступ:** бот публичный (мульти-тенант), доступ — по членству в паре, НЕ по
  whitelist. Любой делает `/start` → создаёт список → шлёт инвайт-ссылку
  (`/start join_<token>`) партнёру → они мэтчатся. Данные строго изолированы по
  `pair_id` (главный security-инвариант, см. `handlers/pairing.py`, `middlewares/auth.py`).
  `ALLOWED_USER_IDS` теперь опционален (для локального bootstrap/тестов).
- **Добавление:** строго пошаговый FSM. Обязательно только название; описание,
  ссылка и фото — опциональны, с кнопкой «Пропустить». В конце — превью + подтверждение.
- **Просмотр:** категория → список записей → карточка с деталями. Навигация «Назад».
- **Категории:** фиксированный базовый набор + пользовательские (видны обоим).
- **Уведомления:** при создании записи партнёру уходит сообщение с превью.
  Логика в `services/notify.py`.
- **Права на правку/удаление:** только автор может редактировать и удалять свои
  записи (own-only). Кнопки действий показываются только для своих записей.

## Мульти-тенантность (на будущее)

Бот задуман с прицелом на публичный запуск: любая пара мэтчится через инвайт-ссылку
(`/start join_<token>`). Поэтому **схема БД проектируется pair-aware с самого начала**
(`pair_id` во всех данных), чтобы потом не делать миграцию.

- Таблицы (закладываются в Спринте 1): `users`, `pairs`, `pair_members`, `invites`;
  у `items` и пользовательских категорий — `pair_id`.
- **Спринт 8 реализован:** онбординг и мэтчинг через инвайт-ссылку работают
  (`handlers/pairing.py`, `services/invite.py`). Whitelist убран. `ALLOWED_USER_IDS`
  в проде пуст — пары создаются самими пользователями.
- Решения: при выходе из пары — **архивация** данных · имена из Telegram `first_name`.
- **Несколько связей (фича на потом, Спринт 10):** один человек может иметь несколько
  отдельных 1-на-1 связей (девушка, друг…), каждая изолирована. Нужен переключатель
  активной связи (`users.current_pair_id`). До этой фичи — одна bootstrap-пара.
- **Security-инвариант:** любой запрос items/категорий/уведомлений фильтруется по
  `pair_id` текущего пользователя. Никакой объект чужой пары не должен утекать.

Полный дизайн — в Obsidian: `Claude Code/our-wants-bot/context/multitenant.md`.

## Конфигурация (.env)

```
BOT_TOKEN=...
ALLOWED_USER_IDS=111111111,222222222
USER_NAME_111111111=Артём
USER_NAME_222222222=Имя
DB_PATH=wants.db
```

## Запуск

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить токен и ID
python bot.py
```

## Команды для проверки

- Запуск: `python bot.py`
- Линт: `ruff check .` (конфиг в `pyproject.toml`)
- Тесты: `pip install -r requirements-dev.txt && pytest`
  Стенд `tests/harness.py` поднимает две мок-сущности (111 «Артём», 222 «Аня»)
  в одной паре и имитирует Telegram (текст/кнопки/фото), перехватывая исходящие
  по chat_id. Так проверяются взаимодействия между двумя пользователями без сети.
  Гонять `pytest` после каждого спринта (самопроверка).
- CI: GitHub Actions (`.github/workflows/ci.yml`) гоняет ruff + pytest на push/PR.
  Пуш — через SSH-remote (OAuth-токен gh без scope `workflow` не пускает workflow по HTTPS).

## После работы

Логируй изменения в `Claude Code/our-wants-bot/daily-changes/YYYY-MM-DD.md`,
обновляй `structure/index.md` при изменении архитектуры.
