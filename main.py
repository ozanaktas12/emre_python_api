from twelvedata import TDClient
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import os as _os  # env için

# --- API KEY ---
API_KEY = _os.getenv("TD_API_KEY", "f3d439499c58455f9460b4f51c376224")
td = TDClient(apikey=API_KEY)

def _safe_float(x, default=None):
    try:
        return float(x)
    except Exception:
        return default

def ath_and_52w(symbol: str, exchange: str | None = None):
    # 1) Günlük barlar
    ts_resp = td.time_series(
        symbol=symbol,
        exchange=exchange,
        interval="1day",
        outputsize=5000,
        order="asc"
    )
    ts_json = ts_resp.as_json()
    if isinstance(ts_json, tuple):
        ts_json = ts_json[0]

    # values çıkarmayı dene; olmazsa pandas fallback
    if isinstance(ts_json, dict):
        values = ts_json.get("values")
    elif isinstance(ts_json, list):
        values = ts_json
    else:
        values = None

    if not values:
        try:
            df_pd = ts_resp.as_pandas().reset_index()
            df_pd = df_pd.rename(columns={
                "datetime": "datetime",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume"
            })
            values = df_pd.to_dict(orient="records")
        except Exception as e:
            raise RuntimeError(f"Time series beklenen formatta dönmedi: {type(ts_json)} - {e}")

    df = pd.DataFrame(values)
    df["high"] = df["high"].astype(float)
    df["close"] = df["close"].astype(float)

    ath = float(df["high"].max())
    last_close = float(df["close"].iloc[-1])

    # 2) 52w high: quote içinden dene; yoksa 252 bar içinden hesapla
    q = td.quote(symbol=symbol, exchange=exchange, interval="1day").as_json()
    wk52_high = None
    if isinstance(q, tuple):
        q = q[0]
    if isinstance(q, dict):
        fw = q.get("fifty_two_week") or {}
        wk52_high = _safe_float(fw.get("high"))
    if wk52_high is None:
        wk52_high = float(df["high"].tail(252).max())

    return {
        "symbol": symbol if exchange is None else f"{symbol}:{exchange}",
        "last_close": last_close,
        "ath": ath,
        "to_ath_pct": round(max(0.0, (ath - last_close) / last_close * 100), 2),
        "wk52_high": wk52_high,
        "to_52w_pct": round(max(0.0, (wk52_high - last_close) / last_close * 100), 2),
    }

app = FastAPI(title="ATH & 52W API", version="0.1.0")

# CORS (63342 vs 8010 gibi farklı portlardan açarsan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://emre-python-api.onrender.com",   # backend (aynı domain)
        # "https://SENIN-VERCEL-ADIN.vercel.app", # (ileride ayrı frontend olursa)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/metrics", response_class=JSONResponse)
def get_metrics(
    symbol: str = Query(..., description="Sembol, örn: THYAO"),
    exchange: str | None = Query("BIST", description="Borsa: BIST ya da NONE")
):
    try:
        ex = exchange if exchange and exchange.upper() != "NONE" else None
        data = ath_and_52w(symbol.strip().upper(), exchange=ex)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/")
def index():
    here = os.path.dirname(__file__)
    return FileResponse(os.path.join(here, "index.html"))

@app.get("/styles.css")
def styles_css():
    here = os.path.dirname(__file__)
    return FileResponse(os.path.join(here, "styles.css"))

# (Opsiyonel) Sağlık
@app.get("/health")
def health():
    return {"ok": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010, reload=True)