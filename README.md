# KisaMore — система управления стеллажами (Raspberry Pi)

KisaMore — это веб-приложение на **Python + FastAPI** для управления стеллажами в теплице
(свет 💡 и полив 💧), рассчитанное на работу с **Raspberry Pi + 12В релейная плата**.

Проект позволяет управлять каждым стеллажом как вручную, так и по расписанию, а также
запускать систему на обычном ПК в режиме эмуляции GPIO для разработки и тестирования.

---

## 🚀 Возможности

- 📊 Веб-панель с карточками стеллажей
- 💡 Управление светом (12В LED-ленты)
- 💧 Управление поливом (12В клапаны)
- 🔀 Режимы работы: **По расписанию / Вручную**
- 🕒 Редактирование расписания через интерфейс (без JSON)
- ⚙️ Гибкая конфигурация оборудования через YAML:
  - количество стеллажей
  - привязка стеллаж → канал реле (1–16)
  - привязка канал реле → GPIO pin Raspberry Pi
- 🧪 Запуск на ПК (Windows / Linux / macOS) в режиме **mock GPIO**
- 🔁 Подготовлено для расширения (датчики, защита насоса, логирование)

---

## 🧩 Архитектура (кратко)

- **Backend**: Python 3.11, FastAPI
- **Frontend**: HTML + CSS + Vanilla JS
- **GPIO**:
  - реальный режим (Raspberry Pi)
  - mock-режим (ПК)
- **База данных**: SQLite (локально)
- **Конфигурация**: YAML (`config/kisamore.yaml`)

Подробное описание архитектуры см. в файле [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 🛠 Установка и запуск (Raspberry Pi)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Открыть в браузере:
- 🌐 Веб-панель: `http://raspberrypi.local:8000/`
- 🔌 API состояния: `http://raspberrypi.local:8000/api/state`

---

## 💻 Запуск на ПК (режим эмуляции GPIO)

Для разработки Raspberry Pi не требуется.

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

При запуске будет выведено:
```
[KisaMore] GPIO disabled (mock mode). Running on non-Raspberry Pi.
```

---

## ⚙️ Конфигурация

Основной конфигурационный файл:
```
config/kisamore.yaml
```

В файле настраивается:
- количество стеллажей
- какой канал реле управляет светом и поливом каждого стеллажа
- какой GPIO pin соответствует каждому каналу реле

Путь к конфигурации можно переопределить:
```bash
export KISAMORE_CONFIG=/path/to/kisamore.yaml
```

---

## 📁 Структура проекта

```
KisaMore/
├── app/                # FastAPI приложение
│   ├── main.py
│   ├── runtime.py
│   ├── gpio_driver.py
│   ├── platform.py
│   ├── routes_*.py
│   ├── static/          # CSS / JS
│   └── templates/       # HTML шаблоны
├── config/
│   └── kisamore.yaml
├── ARCHITECTURE.md
├── DEV_NOTES.md
├── README.md
└── requirements.txt
```

---

## 📝 Примечания

- Файл базы данных SQLite (`*.db`) **не хранится в репозитории**
- Проект рассчитан на постепенное развитие:
  - датчики уровня воды
  - защита насоса от сухого хода
  - лог событий
  - интеграция с Home Assistant / MQTT

---

# 🇬🇧 KisaMore (English – short)

**KisaMore** is a Raspberry Pi based greenhouse rack control system
for light 💡 and watering 💧, built with **Python and FastAPI**.

### Features
- Web dashboard
- Manual and scheduled control
- Flexible hardware configuration (YAML)
- 16-channel relay support
- GPIO mock mode for PC development

### Tech stack
- Python 3.11
- FastAPI
- SQLite
- GPIO (real / mock)

### Run (development)
```bash
uvicorn app.main:app --reload
```

Designed for Raspberry Pi, fully runnable on PC for development and testing.

---

## License

Private / internal project (license to be defined).

---

## Central cloud API (first read-only stage)

The repository now also contains an optional central API for a VPS. The Raspberry Pi makes
outbound authenticated requests; no Pi control endpoints are exposed to the public site.

Deployment and configuration: [`cloud/README.md`](cloud/README.md).
