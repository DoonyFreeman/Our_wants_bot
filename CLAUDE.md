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

- **Доступ:** только 2 Telegram ID из `ALLOWED_USER_IDS`. Middleware `auth.py`
  отклоняет всех остальных. Никогда не отключай этот whitelist.
- **Добавление:** строго пошаговый FSM. Обязательно только название; описание,
  ссылка и фото — опциональны, с кнопкой «Пропустить». В конце — превью + подтверждение.
- **Просмотр:** категория → список записей → карточка с деталями. Навигация «Назад».
- **Категории:** фиксированный базовый набор + пользовательские (видны обоим).
- **Уведомления:** при создании записи партнёру уходит сообщение с превью.
  Логика в `services/notify.py`.
- **Права на правку/удаление:** только автор может редактировать и удалять свои
  записи (own-only). Кнопки действий показываются только для своих записей.

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
- (тесты/линт добавить при реализации, например `ruff check .`)

## После работы

Логируй изменения в `Claude Code/our-wants-bot/daily-changes/YYYY-MM-DD.md`,
обновляй `structure/index.md` при изменении архитектуры.
