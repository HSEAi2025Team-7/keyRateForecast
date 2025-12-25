# FastApi

## Архитектура
```text
Client
  |
  | HTTP
  v
FastAPI
  |
  |-- POST /forward (JSON → ML predict | multipart → image)
  |-- GET  /items   (query params → ML predict)
  |-- GET  /history (read logs)
  |
  |-- ML pipeline: DataFrame → check FEATURES → scale → model.predict
  |-- Image pipeline: PIL → PNG → base64
  |
  └-- Logging → SQLite (history.db)
```
## Вклад участников

**Давыдов Александр**: <br>
- полная реализация route типа POST на /forward;
- реализация и доработка GET-запрос /history

**Гусева Елизавета**: <br>
- подготовка файлов feature_names.json, main.py, model.pkl, scaler.pkl, stand_col.json;
- форматирование кода под принаки: функция предсказания, get items;
- реализация GET-запрос /history
