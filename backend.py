# -*- coding: utf-8 -*-
"""
BIST için iki sembol gir → her biri için temel verileri göster →
küçük olanın büyük olana yetişmesi için gereken X ve % artışı hesapla.
Sadece Twelve Data (REST) kullanır. TD_API_KEY zorunludur.
"""
import os
import json
import requests
from typing import Optional, Dict, Tuple

TD_API_KEY = "f3d439499c58455f9460b4f51c376224"
BASE_URL = "https://api.twelvedata.com"
EXCHANGE = "BIST"  # bu projede yalnızca BIST

def _get(path: str, params: Dict) -> Dict:
    p = dict(params)
    p["apikey"] = TD_API_KEY
    r = requests.get(f"{BASE_URL}/{path}", params=p, timeout=30)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(data.get("message", "TwelveData error"))
    return data

def last_price(symbol: str) -> float:
    # Anlık/snaphot: close/price/last; BIST için exchange parametresi gerekir.
    data = _get("quote", {"symbol": symbol, "exchange": EXCHANGE, "interval": "1day"})
    if isinstance(data, list):
        data = data[0]
    for key in ("close", "price", "last", "last_price"):
        val = data.get(key)
        if val not in (None, "", "NaN"):
            return float(val)
    raise RuntimeError(f"{symbol}: son fiyat bulunamadı: {json.dumps(data)[:200]}")

def market_cap(symbol: str) -> float:
    """
    Market cap'i önce /statistics'ten, yoksa /fundamentals?type=statistics'ten dener.
    Eğer yine yoksa, /profile'dan 'shares_outstanding' alıp son fiyat ile çarpar.
    """
    # 1) /statistics
    params_sym = {"symbol": f"{symbol}:{EXCHANGE}"}
    try:
        stats = _get("statistics", params_sym)
        for key in ("market_cap", "market_capitalization", "marketCapitalization",
                    "market_capitalisation", "marketCapitalization"):
            val = stats.get(key)
            if val not in (None, "", "NaN"):
                try:
                    return float(str(val).replace(",", ""))
                except Exception:
                    pass
    except Exception:
        pass

    # 2) /fundamentals?type=statistics
    try:
        stats2 = _get("fundamentals", {"symbol": f"{symbol}:{EXCHANGE}", "type": "statistics"})
        for key in ("market_cap", "market_capitalization", "marketCapitalization",
                    "market_capitalisation", "marketCapitalization"):
            val = stats2.get(key)
            if val not in (None, "", "NaN"):
                try:
                    return float(str(val).replace(",", ""))
                except Exception:
                    pass
    except Exception:
        pass

    # 3) /profile (shares_outstanding × last_price)
    try:
        prof = _get("profile", {"symbol": f"{symbol}:{EXCHANGE}"})
    except Exception:
        try:
            prof = _get("fundamentals", {"symbol": f"{symbol}:{EXCHANGE}", "type": "profile"})
        except Exception:
            prof = {}
    shares = None
    for k in ("shares_outstanding", "sharesOutstanding", "share_outstanding", "float_shares", "shares"):
        v = prof.get(k)
        if v not in (None, "", "NaN"):
            try:
                shares = float(str(v).replace(",", ""))
                break
            except Exception:
                pass
    if shares is None:
        raise RuntimeError(f"{symbol}: market cap verisi bulunamadı (statistics/profile erişilemedi)")
    lp = last_price(symbol)
    return shares * lp

def fetch_symbol_data(symbol: str) -> Tuple[float, float]:
    """
    Verilen sembol için (market_cap, last_price) döndürür.
    """
    lp = last_price(symbol)
    mc = market_cap(symbol)
    return mc, lp

def compare(a: str, b: str) -> Dict:
    """
    İki sembolü kıyasla: küçük olanın büyük olana yetişmesi için X ve % artış.
    """
    a, b = a.upper().strip(), b.upper().strip()
    mc_a, lp_a = fetch_symbol_data(a)
    mc_b, lp_b = fetch_symbol_data(b)
    # Hangisi büyük?
    if mc_a >= mc_b:
        bigger, smaller = ("A", "B")
        big, small = mc_a, mc_b
    else:
        bigger, smaller = ("B", "A")
        big, small = mc_b, mc_a
    x_needed = big / small
    pct_needed = (x_needed - 1.0) * 100.0
    return {
        "A_symbol": f"{a}:{EXCHANGE}",
        "A_last_price": round(lp_a, 6),
        "A_market_cap": round(mc_a, 2),
        "B_symbol": f"{b}:{EXCHANGE}",
        "B_last_price": round(lp_b, 6),
        "B_market_cap": round(mc_b, 2),
        "bigger": bigger,
        "x_needed_for_smaller_to_match_bigger": round(x_needed, 4),
        "pct_increase_needed_for_smaller_%": round(pct_needed, 2),
    }

if __name__ == "__main__":
    try:
        if not TD_API_KEY:
            raise RuntimeError("TD_API_KEY tanımlı değil. Terminalde `export TD_API_KEY='...'` yap.")
        print("BIST için iki sembolü gir (örn: THYAO, ASTOR).")
        a = input("A sembolü: ").strip().upper()
        b = input("B sembolü: ").strip().upper()

        # (1) Kullanıcının girdiği iki şeyi göster
        print("\n=== Girdi ===")
        print(f"A: {a}:{EXCHANGE}")
        print(f"B: {b}:{EXCHANGE}")

        # (2) Her biri için temel bilgileri göster
        mc_a, lp_a = fetch_symbol_data(a)
        mc_b, lp_b = fetch_symbol_data(b)
        print("\n=== A Bilgileri ===")
        print(f"Sembol: {a}:{EXCHANGE}")
        print(f"Son Fiyat: {lp_a}")
        print(f"Market Cap: {mc_a}")
        print("\n=== B Bilgileri ===")
        print(f"Sembol: {b}:{EXCHANGE}")
        print(f"Son Fiyat: {lp_b}")
        print(f"Market Cap: {mc_b}")

        # (3) Kıyas ve sonuç
        out = compare(a, b)
        print("\n=== Kıyas Sonucu ===")
        print(f"Büyük: {out['bigger']}")
        print(f"X katsayısı: {out['x_needed_for_smaller_to_match_bigger']}")
        print(f"Gerekli % artış: {out['pct_increase_needed_for_smaller_%']}%")

        print("\n=== Ham JSON ===")
        print(json.dumps(out, ensure_ascii=False, indent=2))

    except Exception as e:
        print("Hata:", e)
