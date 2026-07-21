"""
collector.py
Collecteur automatique des vols LFBD (Aéroport de Bordeaux-Mérignac).
- Requêtes HTTP POST asynchrones avec httpx
- Parsing HTML via BeautifulSoup
- Fenêtre glissante : J-1 / J / J+1
- Stockage transactionnel SQLite (UPSERT)

Dépendances : pip install httpx beautifulsoup4
"""

import asyncio
import json
import logging
import random
import sqlite3
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta

from bs4 import BeautifulSoup
import httpx

# --- Configuration ---------------------------------------------------------
BASE_URL = "https://www.bordeaux.aeroport.fr/ajax/flights"
DB_PATH = "lfbd_schedule.db"

POLL_INTERVAL_SECONDS = 300  # 5 minutes entre chaque cycle complet
MAX_RETRIES = 3
BASE_BACKOFF = 2.0
REQUEST_TIMEOUT = 15.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("lfbd-collector")


# --- Schéma SQLite ---------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS flights (
    uid            TEXT PRIMARY KEY,  -- (callsign|scheduled_date|direction)
    callsign       TEXT,
    direction      TEXT,               -- 'in' / 'out'
    scheduled_date TEXT,               -- YYYY-MM-DD
    scheduled_time TEXT,               -- HH:MM
    airline        TEXT,
    origin_dest    TEXT,
    status         TEXT,               -- Statut publié (ex: Prévu, Atterri, Retardé...)
    raw            TEXT,               -- Payload JSON/dict pour traçabilité
    first_seen_at  TEXT,
    last_seen_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_date_dir ON flights (scheduled_date, direction);
CREATE INDEX IF NOT EXISTS idx_status   ON flights (status);

CREATE TABLE IF NOT EXISTS collection_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)


# --- Helpers Normalisation / UID -------------------------------------------
def normalize_callsign(cs: str) -> str:
    return (cs or "").strip().upper().replace(" ", "").replace("-", "")


def build_uid(callsign: str, sched_date_iso: str, direction: str, fallback_time: str = "", fallback_city: str = "") -> str:
    norm_cs = normalize_callsign(callsign)
    if not norm_cs:
        # Fallback de sécurité si le numéro de vol n'est pas renseigné dans le tableau
        norm_cs = f"NO_CS_{fallback_time}_{normalize_callsign(fallback_city)}"
    return f"{norm_cs}|{sched_date_iso}|{direction}"


# --- Scraping HTTP + Parsing HTML ------------------------------------------
async def fetch_day(client: httpx.AsyncClient, day: date, direction: str) -> list[dict]:
    """
    Interroge l'endpoint AJAX pour un jour et un sens ('in' / 'out').
    Date formatée en JJ/MM/AAAA.
    """
    date_fr = day.strftime("%d/%m/%Y")
    params = {
        "w": direction,
        "date": date_fr,
        "time": "00:00",
        "_wrapper_format": "drupal_ajax",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = await client.post(BASE_URL, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            
            # Parsing du JSON Drupal
            data = resp.json()
            return parse_drupal_response(data, day, direction)

        except (httpx.HTTPStatusError, httpx.TransportError, httpx.TimeoutException, json.JSONDecodeError) as e:
            log.warning("Erreur tentative %d/%d (%s %s) : %s", attempt, MAX_RETRIES, direction, date_fr, e)

        if attempt < MAX_RETRIES:
            delay = BASE_BACKOFF * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            await asyncio.sleep(delay)

    log.error("Échec définitif de collecte pour %s (%s).", date_fr, direction)
    return []


def parse_drupal_response(json_payload: list, day: date, direction: str) -> list[dict]:
    """
    Extrait le HTML depuis le payload JSON de Drupal et extrait les lignes du tableau.
    """
    rows = []
    if not isinstance(json_payload, list):
        return rows

    for command in json_payload:
        if isinstance(command, dict) and command.get("command") == "insert" and "data" in command:
            html_content = command["data"]
            soup = BeautifulSoup(html_content, "html.parser")

            for tr in soup.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) >= 4:
                    heure = tds[0].get_text(strip=True)
                    ville = tds[1].get_text(" / ", strip=True)
                    vol = tds[2].get_text(" / ", strip=True)
                    compagnie = tds[3].get_text(" / ", strip=True)
                    statut = tds[5].get_text(strip=True) if len(tds) >= 6 else "Programmé"

                    rows.append({
                        "callsign": vol,
                        "scheduled_time": heure,
                        "origin_dest": ville,
                        "airline": compagnie,
                        "status": statut or "Programmé",
                        "raw": {
                            "heure": heure,
                            "ville": ville,
                            "vol": vol,
                            "compagnie": compagnie,
                            "statut": statut
                        }
                    })
            break  # Commande d'insertion traitée

    return rows


# --- Sauvegarde SQLite Transactionnelle ------------------------------------
def upsert_flights(rows: list[dict], day: date, direction: str):
    now_iso = datetime.utcnow().isoformat(timespec="seconds")
    sched_date_iso = day.isoformat()  # YYYY-MM-DD pour SQLite

    with get_db() as conn:
        for r in rows:
            uid = build_uid(r["callsign"], sched_date_iso, direction, r["scheduled_time"], r["origin_dest"])
            conn.execute("""
                INSERT INTO flights
                    (uid, callsign, direction, scheduled_date, scheduled_time,
                     airline, origin_dest, status, raw, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(uid) DO UPDATE SET
                    scheduled_time = excluded.scheduled_time,
                    airline        = excluded.airline,
                    origin_dest    = excluded.origin_dest,
                    status         = excluded.status,
                    raw            = excluded.raw,
                    last_seen_at   = excluded.last_seen_at
            """, (
                uid,
                normalize_callsign(r["callsign"]),
                direction,
                sched_date_iso,
                r["scheduled_time"],
                r["airline"],
                r["origin_dest"],
                r["status"],
                json.dumps(r["raw"], ensure_ascii=False),
                now_iso,
                now_iso,
            ))

        conn.execute("""
            INSERT INTO collection_meta (key, value) VALUES ('last_success', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (now_iso,))


# --- Boucle principale ------------------------------------------------------
async def collect_once():
    today = date.today()
    window = [today - timedelta(days=1), today, today + timedelta(days=1)]

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for day in window:
            for direction in ("in", "out"):
                rows = await fetch_day(client, day, direction)
                if rows:
                    upsert_flights(rows, day, direction)
                    log.info("✅ %s %s : %d vols synchronisés.", direction.upper(), day.isoformat(), len(rows))
                await asyncio.sleep(1.0)


async def run_forever():
    init_db()
    log.info("🚀 Collecteur LFBD démarré (Intervalle : %ds).", POLL_INTERVAL_SECONDS)
    while True:
        cycle_start = time.monotonic()
        try:
            await collect_once()
        except Exception:
            log.exception("❌ Erreur imprévue pendant le cycle de collecte.")
        
        elapsed = time.monotonic() - cycle_start
        wait_time = max(0.0, POLL_INTERVAL_SECONDS - elapsed)
        await asyncio.sleep(wait_time)


if __name__ == "__main__":
    try:
        asyncio.run(run_forever())
    except KeyboardInterrupt:
        log.info("🛑 Arrêt du collecteur.")
