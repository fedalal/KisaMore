# Dev notes

## Полезные команды

Запуск (dev):
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

Запуск (prod / pi):
uvicorn app.main:app --host 0.0.0.0 --port 8000

## Режим mock GPIO (ПК)
- через env: KISAMORE_GPIO=mock
- или через config (если включено)

## Типовые проблемы
- gpiozero BadPinFactory на ПК → используйте mock режим
