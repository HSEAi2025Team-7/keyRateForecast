from fastapi import FastAPI, Request, Header, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
import base64
from io import BytesIO
from PIL import Image
import joblib
import pandas as pd
import sqlite3
import json

app = FastAPI(title='CBR Press-release Classifier')

#добавлены признаки для стандартизации и для модели
FEATURES = json.load(open("feature_names.json", "r", encoding="utf-8"))
STAND_COL = json.load(open("stand_col.json", "r", encoding="utf-8"))

model = joblib.load("model.pkl")
scaler = joblib.load("scaler.pkl")


# инициализация БД
def init_db():
    conn = sqlite3.connect("history.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT,
            headers TEXT,
            body TEXT
        )
    """
    )
    conn.commit()
    conn.close()
#запуск создания таблиц при запуске приложения
init_db()

# функция предсказания
def predicter(data):
    df = pd.DataFrame([data]) if isinstance(data, dict) else pd.DataFrame(data)
    if df.empty:
        raise ValueError("empty input")

    # проверка состава признаков
    if set(df.columns) != set(FEATURES):
        missing = list(set(FEATURES) - set(df.columns))
        extra = list(set(df.columns) - set(FEATURES))
        raise ValueError(f"bad columns: missing={missing}, extra={extra}")

    # порядок колонок в обучении плюс привеление к типу флоат
    df = df[FEATURES].copy().astype(float)

    # масштабирование части колонок
    df[STAND_COL] = scaler.transform(df[STAND_COL])

    # предикт на всех колонках
    preds = model.predict(df)
    return preds

# функция сохранения в БД
def save_to_db(record: dict):
    conn = sqlite3.connect("history.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO history (path, headers, body)
        VALUES (?, ?, ?)
        """,
        (
            record["path"],
            json.dumps(record["headers"], ensure_ascii=False),
            json.dumps(record["body"], ensure_ascii=False),
        )
    )
    conn.commit()
    conn.close()

# /forward endpoint
@app.post("/forward")
async def forward(
    request: Request,
    image: UploadFile = File(None),
    x_param: str = Header(None),
):

    # если есть файл изображения
    if image:
        try:
            img_bytes = await image.read()
            pil = Image.open(BytesIO(img_bytes))
        except Exception:
            raise HTTPException(status_code=400, detail="bad request")

        # сохраняем в БД
        save_to_db({
            "path": "/forward",
            "headers": dict(request.headers),
            "body": f"image: {image.filename}, header x_param={x_param}"
        })

        try:
            buff = BytesIO()
            pil.save(buff, format="PNG")
            b64 = base64.b64encode(buff.getvalue()).decode()
        except Exception:
            raise HTTPException(
                status_code=403,
                detail="модель не смогла обработать данные"
            )

        return {"image_base64": b64}

    # иначе — ждём JSON
    else:
        content_type = request.headers.get("content-type", "")
        if "json" not in content_type.lower():
            raise HTTPException(status_code=400, detail="bad request")

        try:
            data = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="bad request")

        # сохраняем в БД
        save_to_db({
            "path": "/forward",
            "headers": dict(request.headers),
            "body": data
        })

        try:
            preds = predicter(data)
            result = {"predictions": preds.tolist()}
        except Exception:
            raise HTTPException(
                status_code=403,
                detail="модель не смогла обработать данные"
            )

        return JSONResponse(content=result)

# /items
@app.get("/items")
#расширены признаки из модели
async def list_items(
    request: Request,
    decision_text: float = Query(...),
    key_rate: float = Query(...),
    inflation_lag_1: float = Query(...),
    usd_rate: float = Query(...),
    usd_lag_1: float = Query(...),
    usd_lag_2: float = Query(...),
    usd_lag_3: float = Query(...),
    text_len_tokens: float = Query(...),
    text_unique_tokens: float = Query(...),
    hike_words_count: float = Query(...),
    cut_words_count: float = Query(...),
    cut_words_ratio: float = Query(...),
    hold_words_ratio: float = Query(...),
    hike_minus_cut_ratio: float = Query(...),
):
#расширены признаки из модели
    data = {
        "decision_text": decision_text,
        "key_rate": key_rate,
        "inflation_lag_1": inflation_lag_1,
        "usd_rate": usd_rate,
        "usd_lag_1": usd_lag_1,
        "usd_lag_2": usd_lag_2,
        "usd_lag_3": usd_lag_3,
        "text_len_tokens": text_len_tokens,
        "text_unique_tokens": text_unique_tokens,
        "hike_words_count": hike_words_count,
        "cut_words_count": cut_words_count,
        "cut_words_ratio": cut_words_ratio,
        "hold_words_ratio": hold_words_ratio,
        "hike_minus_cut_ratio": hike_minus_cut_ratio,
    }

    # сохраняем запрос
    save_to_db({
        "path": "/items",
        "headers": dict(request.headers),
        "body": data
    })

    preds = predicter(data)

    return {"result": "обработано", "predictions": preds.tolist()}

# история из БД 
@app.get("/history")
def get_history_db():
    conn = sqlite3.connect("history.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, path, headers, body FROM history")
    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "id": r[0],
            "path": r[1],
            "headers": json.loads(r[2]),
            "body": json.loads(r[3])
        })
    return result
