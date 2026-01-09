# KisaMore (Raspberry Pi)

## Запуск
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Конфиг
Файл: `config/kisamore.yaml`

Можно переопределить путь:
```bash
export KISAMORE_CONFIG=/path/to/kisamore.yaml
```
