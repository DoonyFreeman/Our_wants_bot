# Деплой our-wants-bot на VPS

Бот работает на long polling под systemd, БД — SQLite (`wants.db`), бэкап по cron.

## Первичная установка

```bash
# 1. Зависимости системы
apt update && apt install -y python3 python3-venv python3-pip git

# 2. Код
mkdir -p /root/Projects
cd /root/Projects
git clone git@github.com:DoonyFreeman/Our_wants_bot.git   # или rsync с локали
cd Our_wants_bot

# 3. venv + зависимости
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 4. Конфиг
cp .env.example .env
nano .env          # вписать BOT_TOKEN и ALLOWED_USER_IDS (свой и партнёра)

# 5. systemd-сервис
cp deploy/our-wants-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now our-wants-bot

# 6. Проверка
systemctl status our-wants-bot
journalctl -u our-wants-bot -n 50 --no-pager
```

## Обновление кода

```bash
cd /root/Projects/Our_wants_bot
git pull
.venv/bin/pip install -r requirements.txt
systemctl restart our-wants-bot
```

## Бэкап БД (cron)

`deploy/backup.sh` копирует `wants.db` в `/root/backups/` с датой и чистит старые (>14 дней).

```bash
mkdir -p /root/backups
crontab -l 2>/dev/null | { cat; echo "0 4 * * * /root/Projects/Our_wants_bot/deploy/backup.sh"; } | crontab -
```

## Полезное

- Логи: `journalctl -u our-wants-bot -f`
- Перезапуск: `systemctl restart our-wants-bot`
- Остановка: `systemctl stop our-wants-bot`
- `ALLOWED_USER_IDS` пуст → бот запустится, но никого не пустит (whitelist).
  Узнать свой Telegram ID — у @userinfobot, затем вписать в `.env` и `systemctl restart`.
