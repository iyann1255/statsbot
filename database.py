import json, os, threading
from datetime import datetime, timezone, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "statbot.json")
WIB = timezone(timedelta(hours=7))
_lock = threading.Lock()

# Structure: {"daily_stats": { "chat_id": { "user_id": { "date": { "count":N, "username":"", "full_name":"" } } } },
#             "messages": [ {"chat_id":..., "user_id":..., "username":"", "full_name":"", "date":"", "hour":N} ] }

def _load():
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "r") as f:
            return json.load(f)
    return {"daily_stats": {}, "messages": []}

def _save(db):
    with open(DB_PATH, "w") as f:
        json.dump(db, f, ensure_ascii=False)

def _today_wib():
    return datetime.now(WIB).strftime("%Y-%m-%d")

def init_db():
    with _lock:
        if not os.path.exists(DB_PATH):
            _save({"daily_stats": {}, "messages": []})

def record_message(chat_id: int, user_id: int, username: str, full_name: str, date: str, hour: int):
    cid, uid = str(chat_id), str(user_id)
    with _lock:
        db = _load()
        ds = db["daily_stats"]
        ds.setdefault(cid, {}).setdefault(uid, {})
        if date in ds[cid][uid]:
            ds[cid][uid][date]["count"] += 1
        else:
            ds[cid][uid][date] = {"count": 1, "username": username, "full_name": full_name}
        ds[cid][uid][date]["username"] = username
        ds[cid][uid][date]["full_name"] = full_name
        db["messages"].append({"chat_id": chat_id, "user_id": user_id, "username": username, "full_name": full_name, "date": date, "hour": hour})
        _save(db)

def get_top_members(chat_id: int, limit: int = 10, days: int = 30):
    since = (datetime.now(WIB) - timedelta(days=days)).strftime("%Y-%m-%d")
    db = _load()
    chat = db["daily_stats"].get(str(chat_id), {})
    totals = {}
    for uid, dates in chat.items():
        s = sum(v["count"] for d, v in dates.items() if d >= since)
        if s > 0:
            sample = next(iter(dates.values()))
            totals[uid] = {"user_id": int(uid), "username": sample["username"], "full_name": sample["full_name"], "total": s}
    rows = sorted(totals.values(), key=lambda x: x["total"], reverse=True)[:limit]
    return rows

def get_daily_totals(chat_id: int, days: int = 7):
    since = (datetime.now(WIB) - timedelta(days=days)).strftime("%Y-%m-%d")
    db = _load()
    chat = db["daily_stats"].get(str(chat_id), {})
    by_date = {}
    for uid, dates in chat.items():
        for d, v in dates.items():
            if d >= since:
                by_date[d] = by_date.get(d, 0) + v["count"]
    return [{"date": d, "total": t} for d, t in sorted(by_date.items())]

def get_hourly_stats(chat_id: int, days: int = 7):
    since = (datetime.now(WIB) - timedelta(days=days)).strftime("%Y-%m-%d")
    db = _load()
    by_hour = {}
    for m in db["messages"]:
        if m["chat_id"] == chat_id and m["date"] >= since:
            h = m["hour"]
            by_hour[h] = by_hour.get(h, 0) + 1
    return [{"hour": h, "total": by_hour[h]} for h in sorted(by_hour)]

def get_user_stats(chat_id: int, user_id: int):
    today = _today_wib()
    week_ago = (datetime.now(WIB) - timedelta(days=7)).strftime("%Y-%m-%d")
    db = _load()
    dates = db["daily_stats"].get(str(chat_id), {}).get(str(user_id), {})
    if not dates:
        return {"total": None, "week": None, "today": None}, 1
    total = sum(v["count"] for v in dates.values())
    week = sum(v["count"] for d, v in dates.items() if d >= week_ago)
    today_c = dates.get(today, {}).get("count", 0)
    # rank
    chat = db["daily_stats"].get(str(chat_id), {})
    rank = 1 + sum(1 for uid, ud in chat.items() if uid != str(user_id) and sum(v["count"] for v in ud.values()) > total)
    return {"total": total, "week": week, "today": today_c}, rank

def get_chat_total(chat_id: int):
    db = _load()
    chat = db["daily_stats"].get(str(chat_id), {})
    return sum(v["count"] for uid in chat.values() for v in uid.values())

def get_users_monthly_total(chat_id: int, year: int, month: int, user_ids: list):
    if not user_ids:
        return {}
    prefix = f"{year:04d}-{month:02d}"
    db = _load()
    chat = db["daily_stats"].get(str(chat_id), {})
    result = {}
    for uid in user_ids:
        dates = chat.get(str(uid), {})
        t = sum(v["count"] for d, v in dates.items() if d.startswith(prefix))
        if t:
            result[uid] = t
    return result

def get_unique_users(chat_id: int):
    db = _load()
    return len(db["daily_stats"].get(str(chat_id), {}))

def get_monthly_stats(chat_id: int, year: int, month: int):
    prefix = f"{year:04d}-{month:02d}"
    db = _load()
    chat = db["daily_stats"].get(str(chat_id), {})
    rows = []
    for uid, dates in chat.items():
        for d, v in dates.items():
            if d.startswith(prefix):
                rows.append({"user_id": int(uid), "username": v["username"], "full_name": v["full_name"], "date": d, "total": v["count"]})
    rows.sort(key=lambda x: (x["date"], -x["total"]))
    return rows

def get_db_path():
    return DB_PATH
