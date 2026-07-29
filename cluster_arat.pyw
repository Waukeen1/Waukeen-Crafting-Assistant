# -*- coding: utf-8 -*-
import os
import time
import sys
import threading
import itertools
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
import re
import queue
import json
import requests
from datetime import datetime, timezone
from difflib import get_close_matches
from urllib.parse import quote
from bs4 import BeautifulSoup
from typing import Dict, List


# --- UTF-8 güvenliği ---
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

APP_TITLE = "Large Cluster Scanner — Burak"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLUSTERS_JSON = os.path.join(BASE_DIR, "data", "clusters_with_ids.json")

# ================ TRADE API (embedded) ================
DATA_DIR = os.path.join(BASE_DIR, "data")
STATS_PATH = os.path.join(DATA_DIR, "stats.json")
CLUSTERS_PATH = os.path.join(DATA_DIR, "clusters_with_ids.json")
SCRAPER_OUT_FILE = os.path.join(DATA_DIR, "clusters_with_ids.json")
RATE_LIMIT_STATE_PATH = os.path.join(DATA_DIR, "trade_rate_limit_state.json")

POE_TRADE_BASE = "https://www.pathofexile.com/api/trade"
POE_PUBLIC_API = "http://api.pathofexile.com"


UA = {
    "User-Agent": "Cluster Notable Scanner (utf-8, by Burak+GPT)",
    "From": "burakgundgdu@gmail.com"
}
COOKIES = {"POESESSID": "your_poe_session_id"}

# ================ PROXY CONFIG ================
PROXY_CONFIG_PATH = os.path.join(BASE_DIR, "data", "proxies.json")

def load_proxy_config():
    """proxies.json varsa yükle, yoksa boş döner."""
    if os.path.exists(PROXY_CONFIG_PATH):
        try:
            with open(PROXY_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_proxy_config(entries):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PROXY_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

def build_proxy_url(ip, port, user, password):
    return f"http://{user}:{password}@{ip}:{port}"


# --- Dinamik Rate Limiter ---
class RateLimitedRequester:
    _persist_lock = threading.Lock()

    def __init__(self, headers, cookies, proxies=None):
        self.headers = headers
        self.cookies = cookies
        self.proxies = proxies or {}
        self._search_interval = 5.1
        self._fetch_interval = 0.85
        self._last_search = 0.0
        self._last_fetch = 0.0
        self._search_cooldown_until = 0.0
        self._fetch_cooldown_until = 0.0
        self._search_lock = threading.Lock()
        self._fetch_lock = threading.Lock()
        self._search_logged = False
        self._fetch_logged = False
        self.interval_message = None
        self._rate_identity = self._build_rate_identity()

    @staticmethod
    def _parse_rate_values(raw):
        values = []
        for value in (raw or "").split(","):
            try:
                parts = tuple(int(part) for part in value.strip().split(":"))
            except (TypeError, ValueError):
                continue
            if len(parts) >= 2:
                values.append(parts)
        return values

    @classmethod
    def _calc_interval(cls, raw, safety=0.25):
        try:
            rules = cls._parse_rate_values(raw)
            # Pace against the rolling short-term windows. The long-term
            # allowance is a burst budget, not a mandatory per-request delay;
            # _header_cooldown still stops before any window is exhausted.
            short_intervals = [
                window / max_requests
                for max_requests, window, *_ in rules
                if max_requests > 0 and window <= 300
            ]
            intervals = short_intervals or [
                window / max_requests
                for max_requests, window, *_ in rules
                if max_requests > 0
            ]
            return max(intervals) + safety
        except (TypeError, ValueError):
            return 5.1

    def _build_rate_identity(self):
        proxy_url = self.proxies.get("https") or self.proxies.get("http")
        if not proxy_url:
            return "direct"
        host = proxy_url.rsplit("@", 1)[-1].split("/", 1)[0]
        return f"proxy:{host}"

    @staticmethod
    def _endpoint_name(is_fetch):
        return "fetch" if is_fetch else "search"

    def _read_persisted_next_allowed(self, is_fetch):
        try:
            with self._persist_lock:
                with open(RATE_LIMIT_STATE_PATH, "r", encoding="utf-8") as handle:
                    state = json.load(handle)
            return float(
                state.get(self._rate_identity, {})
                .get(self._endpoint_name(is_fetch), {})
                .get("next_allowed_at", 0.0)
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return 0.0

    def _write_persisted_next_allowed(self, is_fetch, next_allowed_at):
        os.makedirs(DATA_DIR, exist_ok=True)
        with self._persist_lock:
            try:
                with open(RATE_LIMIT_STATE_PATH, "r", encoding="utf-8") as handle:
                    state = json.load(handle)
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                state = {}
            identity_state = state.setdefault(self._rate_identity, {})
            identity_state[self._endpoint_name(is_fetch)] = {
                "next_allowed_at": float(next_allowed_at),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            temp_path = f"{RATE_LIMIT_STATE_PATH}.{os.getpid()}.tmp"
            with open(temp_path, "w", encoding="utf-8") as handle:
                json.dump(state, handle, ensure_ascii=True, indent=2)
            os.replace(temp_path, RATE_LIMIT_STATE_PATH)

    @classmethod
    def _header_cooldown(cls, resp_headers):
        cooldown = 0.0
        for scope in ("Ip", "Account"):
            limits = cls._parse_rate_values(
                resp_headers.get(f"X-Rate-Limit-{scope}", "")
            )
            states = cls._parse_rate_values(
                resp_headers.get(f"X-Rate-Limit-{scope}-State", "")
            )
            for limit, state in zip(limits, states):
                max_requests, window, *_ = limit
                used_requests, _, *state_tail = state
                restricted_for = state_tail[0] if state_tail else 0
                if restricted_for > 0:
                    cooldown = max(cooldown, float(restricted_for) + 1.0)
                # Normal request pacing already respects rolling windows. Only
                # enforce a full cooldown when the server reports a restriction;
                # waiting the entire window at max_requests - 1 needlessly
                # stalls a correctly paced client.
        return cooldown

    def _update_intervals(self, resp_headers, is_fetch=False):
        intervals = []
        for scope in ("Ip", "Account"):
            raw = resp_headers.get(f"X-Rate-Limit-{scope}", "")
            if raw:
                intervals.append(self._calc_interval(raw))
        if not intervals:
            return self._header_cooldown(resp_headers)
        new_interval = max(intervals)
        if is_fetch:
            changed = abs(self._fetch_interval - new_interval) >= 0.01
            self._fetch_interval = max(self._fetch_interval, new_interval)
            if not self._fetch_logged or changed:
                self._fetch_logged = True
                self.interval_message = (
                    f"[Rate] Search interval={self._search_interval:.2f}s  "
                    f"Fetch interval={self._fetch_interval:.2f}s"
                )
        else:
            changed = abs(self._search_interval - new_interval) >= 0.01
            self._search_interval = max(self._search_interval, new_interval)
            if not self._search_logged or changed:
                self._search_logged = True
                self.interval_message = (
                    f"[Rate] Search interval={self._search_interval:.2f}s  "
                    f"Fetch interval={self._fetch_interval:.2f}s"
                )
        return self._header_cooldown(resp_headers)

    @staticmethod
    def _retry_after_seconds(response):
        try:
            return max(1, int(float(response.headers.get("Retry-After", 60))))
        except (TypeError, ValueError):
            return 60

    def _wait_for_slot(self, is_fetch):
        now = time.time()
        last_request = self._last_fetch if is_fetch else self._last_search
        interval = self._fetch_interval if is_fetch else self._search_interval
        cooldown_until = (
            self._fetch_cooldown_until
            if is_fetch
            else self._search_cooldown_until
        )
        persisted = self._read_persisted_next_allowed(is_fetch)
        next_allowed = max(last_request + interval, cooldown_until, persisted)
        remaining = next_allowed - now
        if remaining > 0:
            print(
                f"[Rate] {self._endpoint_name(is_fetch)} "
                f"{remaining:.1f}s bekliyor.",
                flush=True,
            )
            time.sleep(remaining)
        reserved_until = time.time() + interval
        self._write_persisted_next_allowed(is_fetch, reserved_until)

    def _set_cooldown(self, is_fetch, seconds):
        until = time.time() + max(0.0, float(seconds))
        if is_fetch:
            self._fetch_cooldown_until = max(
                self._fetch_cooldown_until, until
            )
            next_allowed = max(
                self._fetch_cooldown_until,
                self._last_fetch + self._fetch_interval,
            )
        else:
            self._search_cooldown_until = max(
                self._search_cooldown_until, until
            )
            next_allowed = max(
                self._search_cooldown_until,
                self._last_search + self._search_interval,
            )
        self._write_persisted_next_allowed(is_fetch, next_allowed)

    def send_request(self, url, data=None, is_fetch=False):
        method = "POST" if data else "GET"
        print(f"[DEBUG] {method} -> {url}")
        rate_lock = self._fetch_lock if is_fetch else self._search_lock
        for attempt in range(1, 4):
            with rate_lock:
                self._wait_for_slot(is_fetch)
                try:
                    response = (
                        requests.post(
                            url,
                            json=data,
                            headers=self.headers,
                            cookies=self.cookies,
                            proxies=self.proxies,
                            timeout=25,
                        )
                        if data
                        else requests.get(
                            url,
                            headers=self.headers,
                            cookies=self.cookies,
                            proxies=self.proxies,
                            timeout=25,
                        )
                    )
                except requests.RequestException as exc:
                    print(f"[API Error] Istek basarisiz ({attempt}/3): {exc}")
                    response = None

                if response is not None:
                    now = time.time()
                    if is_fetch:
                        self._last_fetch = now
                    else:
                        self._last_search = now
                    proactive_cooldown = self._update_intervals(
                        response.headers,
                        is_fetch=is_fetch,
                    )
                    if proactive_cooldown > 0:
                        print(
                            f"[Rate] {self._endpoint_name(is_fetch)} sayaci "
                            f"sinira yaklasti; {proactive_cooldown:.0f}s "
                            "proaktif bekleme ayarlandi.",
                            flush=True,
                        )
                        self._set_cooldown(
                            is_fetch,
                            proactive_cooldown,
                        )
                    else:
                        interval = (
                            self._fetch_interval
                            if is_fetch
                            else self._search_interval
                        )
                        self._write_persisted_next_allowed(
                            is_fetch,
                            now + interval,
                        )

            if response is None:
                if attempt < 3:
                    time.sleep(min(2 ** attempt, 5))
                    continue
                return {}

            if response.status_code == 429:
                retry_after = self._retry_after_seconds(response)
                self._set_cooldown(is_fetch, retry_after + 1)
                print(
                    f"[RATE LIMIT] {retry_after + 1}s bekleniyor "
                    f"({attempt}/3)...",
                    flush=True,
                )
                if attempt < 3:
                    continue
                return {}

            try:
                response_json = response.json()
            except Exception:
                print("[API Error] JSON parse edilemedi:", response.text[:200])
                if attempt < 3 and response.status_code >= 500:
                    time.sleep(min(2 ** attempt, 5))
                    continue
                return {}

            if "error" in response_json:
                err = response_json["error"]
                msg = err.get("message", "") if isinstance(err, dict) else str(err)
                print(f"[API Error] {msg}")
                if attempt < 3 and response.status_code >= 500:
                    time.sleep(min(2 ** attempt, 5))
                    continue
                return {}

            state_ip = response.headers.get("X-Rate-Limit-Ip-State", "?")
            state_acc = response.headers.get(
                "X-Rate-Limit-Account-State", "?"
            )
            print(f"[State] IP={state_ip} | ACC={state_acc}")
            return response_json

        return {}
REQUESTER = RateLimitedRequester(headers=UA, cookies=COOKIES)
_REQUESTERS = [REQUESTER]  # round-robin listesi
_rr_index = 0

def get_next_requester():
    """Round-robin ile sıradaki requester'ı döner."""
    global _rr_index
    r = _REQUESTERS[_rr_index % len(_REQUESTERS)]
    _rr_index += 1
    return r

def reload_requesters(log_fn=None):
    """proxies.json'dan requester listesini yeniden oluşturur."""
    global _REQUESTERS, REQUESTER
    def log(msg):
        if log_fn:
            log_fn(msg)
        else:
            print(msg)
    entries = load_proxy_config()
    if not entries:
        REQUESTER = RateLimitedRequester(headers=UA, cookies=COOKIES)
        _REQUESTERS = [REQUESTER]
        log("[Proxy] Proxy girilmedi — tek hesap, kendi IP ile çalışıyor.")
        return
    lst = []
    for e in entries:
        ip = e.get("ip", "").strip()
        sid = e.get("poesessid", "").strip()
        if not sid or not ip:
            continue
        proxy_url = build_proxy_url(ip, e["port"], e["user"], e["password"])
        proxies = {"http": proxy_url, "https": proxy_url}
        cookies = {"POESESSID": sid}
        lst.append(RateLimitedRequester(headers=UA, cookies=cookies, proxies=proxies))
        log(f"[Proxy] {ip} → POESESSID={sid[:8]}... yüklendi")
    if not lst:
        REQUESTER = RateLimitedRequester(headers=UA, cookies=COOKIES)
        _REQUESTERS = [REQUESTER]
        log("[Proxy] Geçerli proxy bulunamadı — anonim çalışıyor.")
        return
    # Kendi IP'li requester (ip boş olan entry)
    own = next((e for e in entries if not e.get("ip", "").strip() and e.get("poesessid", "").strip()), None)
    if own:
        sid = own["poesessid"].strip()
        lst.append(RateLimitedRequester(headers=UA, cookies={"POESESSID": sid}, proxies={}))
        log(f"[Proxy] Kendi IP → POESESSID={sid[:8]}... yüklendi")
    _REQUESTERS = lst
    REQUESTER = lst[0]
    log(f"[Proxy] Toplam {len(lst)} requester aktif.")


def ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_or_fetch_stats():
    ensure_dirs()
    cached = None
    if os.path.exists(STATS_PATH):
        try:
            with open(STATS_PATH, "r", encoding="utf-8") as f:
                cached = json.load(f)
            cache_age = time.time() - os.path.getmtime(STATS_PATH)
            has_current_cluster_ids = any(
                str(entry.get("id", "")).startswith(
                    "enchant.stat_3948993189|"
                )
                for group in cached.get("result", [])
                for entry in group.get("entries", [])
            )
            if cache_age < 6 * 60 * 60 and has_current_cluster_ids:
                return cached
        except Exception:
            cached = None

    try:
        response = requests.get(
            f"{POE_TRADE_BASE}/data/stats",
            headers=UA,
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        with open(STATS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data
    except Exception:
        if cached is not None:
            return cached
        raise


def get_current_challenge_league_id():
    resp = requests.get(f"{POE_PUBLIC_API}/leagues?type=main", headers=UA, timeout=10)
    resp.raise_for_status()
    leagues = resp.json()
    bad_tokens = ("Standard", "Hardcore", "SSF", "Ruthless")
    candidates = [lg for lg in leagues if not any(tok in lg.get("id", "") for tok in bad_tokens) and not lg.get("event")]
    candidates.sort(key=lambda lg: lg.get("startAt") or "", reverse=True)
    return candidates[0]["id"] if candidates else leagues[0]["id"]


def get_divine_chaos_rate_from_trade(league_id):
    body = {
        "exchange": {
            "status": {"option": "securable"},
            "have": ["divine"],
            "want": ["chaos"],
        }
    }
    try:
        response = requests.post(
            f"{POE_TRADE_BASE}/exchange/{league_id}",
            json=body,
            headers=UA,
            timeout=20,
        )
        response.raise_for_status()
        results = response.json().get("result", {})
    except Exception:
        return None

    ratios = []
    iterable = results.values() if isinstance(results, dict) else results
    for result in iterable:
        for offer in result.get("listing", {}).get("offers", []):
            exchange = offer.get("exchange", {})
            item = offer.get("item", {})
            if exchange.get("currency") != "divine" or item.get("currency") != "chaos":
                continue
            try:
                ratio = float(item["amount"]) / float(exchange["amount"])
                stock = int(item.get("stock", 0))
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                continue
            if 10 <= ratio <= 10000 and stock >= 10:
                ratios.append(ratio)
            if len(ratios) >= 5:
                break
        if len(ratios) >= 5:
            break

    if not ratios:
        return None
    ordered = sorted(ratios)
    return float(ordered[len(ordered) // 2])


def get_currency_rates_chaos(league_id):
    url = f"https://poe.ninja/api/data/currencyoverview?league={league_id}&type=Currency"
    try:
        resp = requests.get(url, headers=UA, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        data = {}
    lines = data.get("lines", [])
    rates = {"chaos": 1.0}
    for c in lines:
        n, ch = c.get("currencyTypeName"), c.get("chaosEquivalent")
        if n and ch:
            rates[n.lower()] = float(ch)
    if "divine orb" in rates and "divine" not in rates:
        rates["divine"] = rates["divine orb"]
    if "divine" not in rates:
        trade_rate = get_divine_chaos_rate_from_trade(league_id)
        if trade_rate:
            rates["divine"] = trade_rate
            rates["divine orb"] = trade_rate
    return rates


def load_clusters_with_ids():
    if not os.path.exists(CLUSTERS_PATH):
        raise FileNotFoundError("data/clusters_with_ids.json bulunamadı.")
    with open(CLUSTERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def find_cluster_by_name(clusters, name):
    for c in clusters:
        if c["clusterName"].strip().lower() == name.strip().lower():
            return c
    return None


def resolve_notable_ids_from_file(clusters, cluster_name, notable_names):
    cluster = find_cluster_by_name(clusters, cluster_name)
    if not cluster:
        return []
    ids = []
    for n in notable_names:
        for nn in cluster["notables"]:
            if nn["notableName"].lower() == n.lower():
                ids.append(nn["notableId"])
                break
    return ids if len(ids) == len(notable_names) else []


def _canonical_cluster_text(text):
    text = re.sub(
        r"Added Small Passive Skills grant:\s*",
        "",
        text or "",
        flags=re.I,
    )
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def find_cluster_option_id(stats, cluster_name):
    ench = next(
        (s for s in stats.get("result", []) if s.get("label") == "Enchant"),
        None,
    )
    if not ench:
        return None

    cluster_norm = _canonical_cluster_text(cluster_name)
    entries = ench.get("entries", [])

    # Current trade API exposes every cluster base as its own stat ID.
    for entry in entries:
        entry_id = entry.get("id", "")
        if not entry_id.startswith("enchant.stat_3948993189|"):
            continue
        if _canonical_cluster_text(entry.get("text", "")) == cluster_norm:
            return entry_id

    # Backward compatibility for cached stats using one stat plus options.
    target = next(
        (e for e in entries if e.get("id") == "enchant.stat_3948993189"),
        None,
    )
    options = (target.get("option") or {}).get("options", []) if target else []
    for option in options:
        if _canonical_cluster_text(option.get("text", "")) == cluster_norm:
            return option["id"]

    option_texts = [_canonical_cluster_text(o.get("text", "")) for o in options]
    close = get_close_matches(cluster_norm, option_texts, n=1, cutoff=0.95)
    if close:
        for option, normalized in zip(options, option_texts):
            if normalized == close[0]:
                return option["id"]
    return None


def build_cluster_base_filter(cluster_option_id):
    option_id = str(cluster_option_id or "")
    if option_id.startswith("enchant.stat_3948993189|"):
        return {"id": option_id}
    return {
        "id": "enchant.stat_3948993189",
        "value": {"option": cluster_option_id},
    }


def _format_age(iso_time):
    """ISO time → '45m', '3h', '2d'"""
    try:
        dt = datetime.strptime(iso_time, "%Y-%m-%dT%H:%M:%S%z")
        diff = datetime.now(timezone.utc) - dt
        minutes = diff.total_seconds() / 60
        if minutes < 60:
            return f"{int(minutes)}m"
        hours = minutes / 60
        if hours < 24:
            return f"{int(hours)}h"
        days = hours / 24
        return f"{int(days)}d"
    except Exception:
        return "?"


def search_large_cluster_combination(league_id, stats, cluster_option_id, notable_ids, rates, max_fetch=10, requester=None):
    filters = [{"id": nid} for nid in notable_ids]
    filters.append(build_cluster_base_filter(cluster_option_id))
    filters.append({"id": "enchant.stat_3086156145", "value": {"min": 8, "max": 8}})

    body = {
        "query": {
            "status": {"option": "securable"},
            "type": "Large Cluster Jewel",
            "stats": [{"type": "and", "filters": filters}],
            "filters": {
                "type_filters": {"filters": {"rarity": {"option": "nonunique"}}},
                "trade_filters": {"filters": {"sale_type": {"option": "priced"}}}
            }
        },
        "sort": {"price": "asc"}
    }

    req = requester if requester is not None else get_next_requester()
    search = req.send_request(f"{POE_TRADE_BASE}/search/{league_id}", data=body)
    if not search:
        raise RuntimeError("Trade search başarısız; sonuç fiyat olarak kaydedilmedi.")

    total = int(search.get("total", 0))
    qid = search.get("id")
    ids = search.get("result", [])[:max_fetch]
    if total <= 0 or not ids:
        print("[⚠️] 0 ilan bulundu.")
        return (0.0, 0.0, 0.0, total, f"https://www.pathofexile.com/trade/search/{league_id}/{qid}", None, None)

    joined = ",".join(ids)
    fetch_url = f"{POE_TRADE_BASE}/fetch/{quote(joined)}?query={quote(qid)}"
    fetch = req.send_request(fetch_url, is_fetch=True)
    if not fetch:
        raise RuntimeError("Trade fetch başarısız; sonuç fiyat olarak kaydedilmedi.")

    results = fetch.get("result", [])
    prices, ages = [], []

    for r in results:
        try:
            li = r["listing"]["price"]
            amount = float(li["amount"])
            curr = li["currency"].lower()
            chaos = amount * rates.get(curr, 1.0)
            if chaos > 0:
                prices.append(chaos)
                ages.append(_format_age(r["listing"]["indexed"]))
        except Exception:
            continue

    if not prices:
        print("[Debug] Fetch sonucu boş — ilan yok veya parse hatası.")
        return (0.0, 0.0, 0.0, total, f"https://www.pathofexile.com/trade/search/{league_id}/{qid}", None, None)

    cheapest = min(prices)
    max_price = max(prices)
    avg_price = sum(prices) / len(prices)

    def _avg_age_str(age_list):
        vals = []
        for a in age_list:
            if a.endswith("m"): vals.append(int(a[:-1]) / 60)
            elif a.endswith("h"): vals.append(int(a[:-1]))
            elif a.endswith("d"): vals.append(int(a[:-1]) * 24)
        if not vals: return "?"
        avg_h = sum(vals) / len(vals)
        if avg_h < 1: return f"{int(avg_h * 60)}m"
        if avg_h < 24: return f"{int(avg_h)}h"
        return f"{int(avg_h / 24)}d"

    cheapest_age = ages[prices.index(cheapest)] if ages else "?"
    avg_age = _avg_age_str(ages)

    print(
        f"[OK] {len(prices)} ilan bulundu | Min={cheapest:.1f}c | "
        f"Max={max_price:.1f}c | Ort={avg_price:.1f}c | Yas={cheapest_age}/{avg_age}"
    )
    trade_link = f"https://www.pathofexile.com/trade/search/{league_id}/{qid}"
    return (cheapest, max_price, avg_price, total, trade_link, cheapest_age, avg_age)

# ================ POEDB SCRAPER (embedded) ================
"""
poedb_scraper.py – Large Cluster Jewel scraper (enchant ID'li)
- PoEDB'den Large Cluster kategorilerini ve notabları çeker
- Her notable için trade/data/stats içinden '1 Added Passive Skill is {name}' metnine karşılık gelen enchant ID'yi bulur
- Sonuç: data/large_notables.json
"""

from bs4 import BeautifulSoup

POEDB_URL = "https://poedb.tw/us/Large_Cluster_Jewel#EnchantmentModifiers"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}


def fetch_trade_stats_cache() -> Dict:
    """stats.json'u data/ altına cache eder ve döner. load_or_fetch_stats kullanır."""
    return load_or_fetch_stats()

def build_enchant_lookup(stats_json: Dict) -> Dict[str, str]:
    """
    '1 Added Passive Skill is {Notable}' -> 'enchant.stat_xxxxx' id sözlüğü oluşturur.
    """
    lookup = {}
    groups = stats_json.get("result", [])
    for g in groups:
        if g.get("label") not in ("Explicit", "Enchant"):
            continue
        for e in g.get("entries", []):
            txt = e.get("text", "")
            eid = e.get("id", "")
            if (
                txt.startswith("1 Added Passive Skill is ")
                and eid.startswith(("explicit.stat_", "enchant.stat_"))
            ):
                notable_name = txt.replace("1 Added Passive Skill is ", "").strip()
                lookup[notable_name] = eid
    return lookup

def scrape_large_clusters(enchant_lookup: Dict[str, str]) -> List[Dict]:
    r = requests.get(POEDB_URL, headers=HEADERS)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    table = soup.find(id="EnchantmentModifiers")
    if not table:
        raise RuntimeError("PoEDB yapısı değişmiş olabilir: EnchantmentModifiers tablosu yok.")

    clusters = []
    buttons = table.find_all("button")
    for btn in buttons:
        parent = btn.find_parent("td")
        if not parent:
            continue

        # kategori başlığı (örn: "Axe ... Sword ...")
        cluster_name = parent.contents[0].text.strip().split("(")[0].strip()
        if not cluster_name:
            continue

        # notable satırlarının olduğu tablo
        tbody = parent.find_next("tbody")
        if not tbody:
            continue

        notables = []
        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue

            # İsmi düzgün çek
            name_parts = list(tds[0].stripped_strings)
            if not name_parts:
                continue
            name = name_parts[-1].strip()
            weight_txt = tds[1].text.strip()
            level_txt = tds[2].text.strip()
            side_txt = tds[3].text.strip().lower()  # prefix/suffix

            # gereksiz satırları ele
            if (
                not name
                or "Added Small Passive Skills also grant" in name
                or "%" in name
                or "increased" in name.lower()
                or "reduced" in name.lower()
            ):
                continue

            if not weight_txt.isdigit():
                continue
            weight = int(weight_txt)

            try:
                level = int(level_txt)
            except:
                continue

            # enchant ID'yi lookup'tan çek
            notable_id = enchant_lookup.get(name, "")
            notables.append({
                "notableName": name,
                "weight": weight,
                "level": level,
                "side": side_txt,
                "notableId": notable_id  # boş olabilir (nadir isim uyuşmazlığı)
            })

        if not notables:
            continue

        clusters.append({
            "clusterName": cluster_name,
            "notables": notables
        })

    return clusters

def scraper_main():
    ensure_dirs()
    stats = fetch_trade_stats_cache()
    lookup = build_enchant_lookup(stats)
    clusters = scrape_large_clusters(lookup)

    with open(SCRAPER_OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(clusters, f, ensure_ascii=False, indent=2)

    print(f"✅ {len(clusters)} cluster kaydedildi → {SCRAPER_OUT_FILE}")
    missing = sum(1 for c in clusters for n in c["notables"] if not n.get("notableId"))
    if missing:
        print(f"⚠️ {missing} notable için enchant id bulunamadı (isim uyuşmazlığı olabilir).")



# ================ SMALL PASSIVE STATS (35% Effect Scanner) ================
EFFECT_STAT_ID = "enchant.stat_3948993189"   # cluster base enchant
SMALL_PASSIVE_EFFECT_ID = "explicit.stat_2618549697"  # 35% increased effect (prefix, sabit)
# NOT: 35% effect stat id trade API'den runtime'da bulunacak

SMALL_PASSIVE_STATS = [
    # (kısa_ad, stat_id, min_değer, side, oyun_tam_metni)
    # ── PREFIX ──
    ("increased Damage",     "explicit.stat_1719521705", 4,  "prefix", "Added Small Passive Skills also grant: #% increased Damage"),
    ("Maximum ES",           "explicit.stat_2643685329", 10, "prefix", "Added Small Passive Skills also grant: +# to Maximum Energy Shield"),
    ("Maximum Life",         "explicit.stat_3819827377", 8,  "prefix", "Added Small Passive Skills also grant: +# to Maximum Life"),
    ("Maximum Mana",         "explicit.stat_3994193163", 9,  "prefix", "Added Small Passive Skills also grant: +# to Maximum Mana"),
    # ── SUFFIX ──
    ("Attack Speed",         "explicit.stat_1411310186", 3,  "suffix", "Added Small Passive Skills also grant: #% increased Attack Speed"),
    ("Cast Speed",           "explicit.stat_1195353227", 3,  "suffix", "Added Small Passive Skills also grant: #% increased Cast Speed"),
    ("Minions A&C Speed",    "explicit.stat_2310019673", 3,  "suffix", "Added Small Passive Skills also grant: Minions have #% increased Attack and Cast Speed"),
    ("A&C Speed Chaos",      "explicit.stat_3692167527", 3,  "suffix", "Added Small Passive Skills also grant: #% increased Attack and Cast Speed with Chaos Skills"),
    ("A&C Speed Cold",       "explicit.stat_2054530657", 3,  "suffix", "Added Small Passive Skills also grant: #% increased Attack and Cast Speed with Cold Skills"),
    ("A&C Speed Elemental",  "explicit.stat_2699118751", 3,  "suffix", "Added Small Passive Skills also grant: #% increased Attack and Cast Speed with Elemental Skills"),
    ("A&C Speed Fire",       "explicit.stat_1849042097", 3,  "suffix", "Added Small Passive Skills also grant: #% increased Attack and Cast Speed with Fire Skills"),
    ("A&C Speed Lightning",  "explicit.stat_201731102",  3,  "suffix", "Added Small Passive Skills also grant: #% increased Attack and Cast Speed with Lightning Skills"),
    ("A&C Speed Physical",   "explicit.stat_1903097619", 3,  "suffix", "Added Small Passive Skills also grant: #% increased Attack and Cast Speed with Physical Skills"),
    ("All Attributes",       "explicit.stat_4036575250", 4,  "suffix", "Added Small Passive Skills also grant: +# to All Attributes"),
    ("Dexterity",            "explicit.stat_2090413987", 6,  "suffix", "Added Small Passive Skills also grant: +# to Dexterity"),
    ("Strength",             "explicit.stat_3258414199", 6,  "suffix", "Added Small Passive Skills also grant: +# to Strength"),
    ("Intelligence",         "explicit.stat_724930776",  6,  "suffix", "Added Small Passive Skills also grant: +# to Intelligence"),
    ("all Elemental Res",    "explicit.stat_2669029667", 4,  "suffix", "Added Small Passive Skills also grant: +#% to all Elemental Resistances"),
    ("Chaos Res",            "explicit.stat_1811604576", 5,  "suffix", "Added Small Passive Skills also grant: +#% to Chaos Resistance"),
    ("Fire Res",             "explicit.stat_1790411851", 6,  "suffix", "Added Small Passive Skills also grant: +#% to Fire Resistance"),
    ("Cold Res",             "explicit.stat_2709692542", 6,  "suffix", "Added Small Passive Skills also grant: +#% to Cold Resistance"),
    ("Lightning Res",        "explicit.stat_2250780084", 6,  "suffix", "Added Small Passive Skills also grant: +#% to Lightning Resistance"),
]

def find_effect_stat_id(stats_json):
    """'35% increased Effect' stat ID'sini trade stats'tan bul."""
    for g in stats_json.get("result", []):
        for e in g.get("entries", []):
            txt = e.get("text", "")
            eid = e.get("id", "")
            if "increased Effect of" in txt and "Cluster Jewel" in txt and eid.startswith("explicit."):
                return eid
    # fallback — bilinen ID
    return "explicit.stat_2618549697"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1100x1000")
        self.minsize(1500, 640)

        self.league_id = None
        self.stats = None
        self.rates = None
        self.clusters = None
        self.paused = False
        self._stop_flag = False

        # Filtre/reset için tam tablo önbelleği
        # Satir yapisi: (check, combo, min, max, avg, listings, age_min, age_avg10, link)
        self._all_rows_cache = []
        self._scan_mode = "notable"   # "notable" | "effect"
        self._effect_stat_id = None   # 35% effect stat ID (runtime'da bulunur)

        self._build_ui()

        # sadece 1 kez bilgi mesajı ve 1 bootstrap thread
        self._log("[Hazır] Önce cluster kategorisi seçin.")
        self._log("[İpucu] Arama sırasında ⏸ Duraklat / ▶ Devam Et tuşunu kullanabilirsin.")

        threading.Thread(target=self._bootstrap_worker, daemon=True).start()

    # --- UI ---
    def _build_ui(self):
        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)

        # Üst bar
        top = ttk.Frame(root)
        top.pack(fill="x", pady=(0, 4))

        self.league_var = tk.StringVar(value="(detecting...)")
        ttk.Label(top, text="League:", width=8).pack(side="left")
        ttk.Label(top, textvariable=self.league_var, width=16).pack(side="left")

        ttk.Label(top, text="   Large Cluster:").pack(side="left")
        self.cluster_var = tk.StringVar()
        self.cluster_combo = ttk.Combobox(top, textvariable=self.cluster_var, state="readonly", width=40)
        self.cluster_combo.pack(side="left", padx=6, expand=True, fill="x")

        # Butonlar
        self.btn_proxy_settings = ttk.Button(top, text="⚙ Proxy/Session", command=self._open_proxy_settings, state="normal")
        self.btn_proxy_settings.pack(side="right", padx=(0, 6))
        self.btn_export = ttk.Button(top, text="💾 CSV Export", command=self._export_csv, state="normal")
        self.btn_export.pack(side="right", padx=(0, 6))
        self.btn_import = ttk.Button(top, text="📥 CSV Import", command=self._import_csv, state="normal")
        self.btn_import.pack(side="right", padx=(0, 6))
        self.btn_template = ttk.Button(top, text="📋 Template Export", command=self._export_template, state="normal")
        self.btn_template.pack(side="right", padx=(0, 6))
        self.btn_frac_scan = ttk.Button(top, text="🔍 Frac Base", command=self._scan_fractured_bases, state="normal")
        self.btn_frac_scan.pack_forget()  # Başlangıçta gizli

        self.btn_refresh = ttk.Button(top, text="Yenile", command=self._reload_everything, state="disabled")
        self.btn_refresh.pack(side="right", padx=(0, 6))

        self.btn_stop = ttk.Button(top, text="■ Bitir", command=self._stop_search, state="disabled")
        self.btn_stop.pack(side="right", padx=(0, 6))

        self.btn_pause = ttk.Button(top, text="⏸ Duraklat", command=self.toggle_pause, state="disabled")
        self.btn_pause.pack(side="right", padx=(0, 6))

        self.btn_start = ttk.Button(top, text="► Başlat", command=self.start_search, state="disabled")
        self.btn_start.pack(side="right", padx=(0, 6))

        self.search_var = tk.StringVar()

        # Mod seçici — top'un hemen altı
        mode_frame = ttk.Frame(root)
        mode_frame.pack(fill="x", pady=(0, 0))
        self._mode_var = tk.StringVar(value="notable")
        ttk.Radiobutton(mode_frame, text="Notable Scanner", variable=self._mode_var,
                        value="notable", command=self._on_mode_change).pack(side="left", padx=(0,6))
        ttk.Radiobutton(mode_frame, text="35% Effect Scanner (12 Passive / iLvl 84+)", variable=self._mode_var,
                        value="effect", command=self._on_mode_change).pack(side="left", padx=(0,8))

        # Effect container — her zaman bu pozisyonda, içi gösterilip gizlenir
        self._effect_container = ttk.Frame(root)
        self._effect_container.pack(fill="x", pady=(0,0))
        self.effect_panel = ttk.Frame(self._effect_container)
        self._build_effect_panel()

        # Tablo
        main_frame = ttk.Frame(root)
        main_frame.pack(fill="both", expand=True, pady=(2, 0))
        self.table_frame = ttk.Frame(main_frame)
        self.table_frame.pack(side="left", fill="both", expand=True)
        table_frame = self.table_frame

        self.columns = (
            "check",            # ✓ / ''
            "combination",
            "cheapest_chaos",
            "max_chaos",
            "avg_chaos",
            "listings",
            "age_cheapest",
            "age_avg10",
            "link",
        )
        self.tree = ttk.Treeview(table_frame, columns=self.columns, show="headings", height=14)

        self.tree.heading("check", text="✓")
        self.tree.heading("combination", text="Kombinasyon",
                          command=lambda: self._sort_tree("combination", False))
        self.tree.heading("cheapest_chaos", text="En Ucuz (chaos)",
                          command=lambda: self._sort_tree("cheapest_chaos", False))
        self.tree.heading("max_chaos", text="Ilk 10 Maks (chaos)",
                          command=lambda: self._sort_tree("max_chaos", False))
        self.tree.heading("avg_chaos", text="Ortalama (chaos)",
                          command=lambda: self._sort_tree("avg_chaos", False))
        self.tree.heading("listings", text="İlan",
                          command=lambda: self._sort_tree("listings", False))
        self.tree.heading("age_cheapest", text="Yaş (en ucuz)",
                          command=lambda: self._sort_tree("age_cheapest", False))
        self.tree.heading("age_avg10", text="Yaş (ilk 10 ort.)",
                          command=lambda: self._sort_tree("age_avg10", False))
        self.tree.heading("link", text="PoE Trade Link")

        self.tree.column("check", width=26, anchor="center", stretch=False)
        self.tree.column("combination", width=420, anchor="w")
        self.tree.column("cheapest_chaos", width=120, anchor="center")
        self.tree.column("max_chaos", width=135, anchor="center")
        self.tree.column("avg_chaos", width=140, anchor="center")
        self.tree.column("listings", width=70, anchor="center")
        self.tree.column("age_cheapest", width=120, anchor="center")
        self.tree.column("age_avg10", width=140, anchor="center")
        self.tree.column("link", width=310, anchor="w")

        self.tree.pack(side="left", fill="both", expand=True)
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        # Etkileşimler
        self.tree.bind("<Double-1>", self._on_tree_double_click_link_only)
        self.tree.bind("<Button-1>", self._on_click_maybe_toggle_checkbox)

        # LOG
        log_frame = ttk.Frame(root)
        log_frame.pack(fill="both", expand=False, pady=(8, 0))
        ttk.Label(log_frame, text="Log:", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.log = tk.Text(log_frame, height=10, wrap="none", font=("Consolas", 10))
        self.log.pack(fill="x", expand=False)

    def _build_effect_panel(self):
        f = self.effect_panel
        self._effect_checks = {}
        prefixes = [(n,sid,d,s) for n,sid,d,s,_ in SMALL_PASSIVE_STATS if s=="prefix"]
        suffixes = [(n,sid,d,s) for n,sid,d,s,_ in SMALL_PASSIVE_STATS if s=="suffix"]

        for row, (name, stat_id, default, _) in enumerate(prefixes):
            chk = tk.BooleanVar(value=True)
            mn  = tk.IntVar(value=default)
            ttk.Checkbutton(f, text=f"[P] {name}", variable=chk).grid(
                row=row, column=0, sticky="w", padx=(2,0), pady=2)
            ttk.Entry(f, textvariable=mn, width=3, justify="center").grid(
                row=row, column=1, padx=(2,2), pady=2)
            self._effect_checks[stat_id] = (chk, mn)

        for idx, (name, stat_id, default, _) in enumerate(suffixes):
            row = idx % 4
            col = 2 + (idx // 4) * 2
            chk = tk.BooleanVar(value=True)
            mn  = tk.IntVar(value=default)
            ttk.Checkbutton(f, text=f"[S] {name}", variable=chk).grid(
                row=row, column=col, sticky="w", padx=(2,0), pady=2)
            ttk.Entry(f, textvariable=mn, width=3, justify="center").grid(
                row=row, column=col+1, padx=(2,2), pady=2)
            self._effect_checks[stat_id] = (chk, mn)

    def _on_mode_change(self):
        """Mod değişince stat panelini göster/gizle."""
        mode = self._mode_var.get()
        self._scan_mode = mode
        if mode == "effect":
            self.effect_panel.pack(fill="x", pady=(1,1))
            self.btn_template.config(text="📋 Effect Template Export", command=self._export_effect_template)
            self.btn_frac_scan.pack(in_=self.btn_template.master, side="right", padx=(0, 6), before=self.btn_template)
        else:
            self.effect_panel.pack_forget()
            self.btn_template.config(text="📋 Template Export", command=self._export_template)
            if hasattr(self, 'btn_frac_scan'):
                self.btn_frac_scan.pack_forget()

    def _export_effect_template(self):
        """Notable export gibi — fiyata göre effect35 kombinasyonları template'e döker."""
        try:
            import json as _json

            all_iids = list(self.tree.get_children())
            if not all_iids:
                self._log("[⚠️] Tabloda veri yok.")
                return

            # ── ADIM 1: Mod seçimi ──────────────────────────────────────────
            mode_dialog = tk.Toplevel(self)
            mode_dialog.title("Effect Template Export")
            mode_dialog.geometry("320x170")
            mode_dialog.resizable(False, False)
            mode_dialog.grab_set()
            ttk.Label(mode_dialog, text="Hangi kombinasyonları dahil etmek istiyorsun?",
                      wraplength=290).pack(pady=(14, 10))
            mode = [None]

            def pick(m):
                mode[0] = m
                mode_dialog.destroy()

            bf0 = ttk.Frame(mode_dialog)
            bf0.pack()
            ttk.Button(bf0, text="✓ Sadece Tikliler",            width=26, command=lambda: pick("checked")).pack(pady=3)
            ttk.Button(bf0, text="💰 Sadece Fiyata Göre",        width=26, command=lambda: pick("price")).pack(pady=3)
            ttk.Button(bf0, text="✓+💰 Hem Tikliler Hem Fiyat", width=26, command=lambda: pick("both")).pack(pady=3)
            mode_dialog.wait_window()
            if mode[0] is None:
                return

            # ── ADIM 2: Chaos eşiği (fiyat modu varsa) ─────────────────────
            threshold = None
            if mode[0] in ("price", "both"):
                pd2 = tk.Toplevel(self)
                pd2.title("Chaos Eşiği")
                pd2.geometry("300x110")
                pd2.resizable(False, False)
                pd2.grab_set()
                ttk.Label(pd2, text="Minimum 'En Ucuz' chaos değeri girin:").pack(pady=(16, 4))
                tvar = tk.StringVar(value="300")
                ent = ttk.Entry(pd2, textvariable=tvar, width=16, justify="center")
                ent.pack()
                ent.focus()
                conf = [False]

                def ok(e=None):
                    conf[0] = True
                    pd2.destroy()

                bf2 = ttk.Frame(pd2)
                bf2.pack(pady=8)
                ttk.Button(bf2, text="Tamam", command=ok, width=10).pack(side="left", padx=4)
                ttk.Button(bf2, text="İptal", command=pd2.destroy, width=10).pack(side="left", padx=4)
                ent.bind("<Return>", ok)
                pd2.wait_window()
                if not conf[0]:
                    return
                try:
                    threshold = float(tvar.get().strip())
                except ValueError:
                    self._log("[⚠️] Geçersiz sayı.")
                    return

            # ── Kombinasyonları topla ────────────────────────────────────────
            seen = set()
            filtered = []

            def add_row(vals):
                key = vals[1]
                if key not in seen:
                    seen.add(key)
                    filtered.append(vals)

            if mode[0] in ("checked", "both"):
                for iid in all_iids:
                    vals = self.tree.item(iid, "values")
                    if vals and vals[0] == "✓":
                        add_row(vals)

            if mode[0] in ("price", "both"):
                for iid in all_iids:
                    vals = self.tree.item(iid, "values")
                    if not vals or len(vals) < 3:
                        continue
                    try:
                        if float(vals[2]) >= threshold:
                            add_row(vals)
                    except (ValueError, IndexError):
                        continue

            if not filtered:
                self._log("[⚠️] Seçilen kriterlere uyan kombinasyon bulunamadı.")
                return

            # stat lookup
            stat_lookup = {name: (sid, minv, side, fulltext) for name, sid, minv, side, fulltext in SMALL_PASSIVE_STATS}
            all_stat_names = ["35% increased Effect"] + [name for name, *_ in SMALL_PASSIVE_STATS]

            def fmt(name):
                if name == "35% increased Effect":
                    return "[P][1] Added Small Passive Skills have #% increased Effect(35)"
                info = stat_lookup.get(name)
                if info:
                    _, minv, side, fulltext = info
                    tag = "P" if side == "prefix" else "S"
                    normalized = re.sub(r'\d+', '#', fulltext)
                    return f"[{tag}][1] {normalized}({minv})"
                return f"[S][1] {name}"

            def fmt_effect(name):
                """Effect35 için mod formatı — parantez içinde minimum roll"""
                return fmt(name)

            # ── Wizard adımları ──────────────────────────────────────────────
            def run_effect_wizard_step(title, description, mode_pair=False, show_oto=False):
                result_items = []
                pair_buffer = []
                cancelled = [False]

                dlg = tk.Toplevel(self)
                dlg.title(title)
                dlg.geometry("520x420")
                dlg.resizable(True, True)
                dlg.grab_set()

                ttk.Label(dlg, text=description, wraplength=490, justify="left").pack(fill="x", padx=12, pady=(12, 6))

                sf = ttk.Frame(dlg)
                sf.pack(fill="x", padx=12, pady=(0, 4))
                ttk.Label(sf, text="Ara:").pack(side="left")
                search_v = tk.StringVar()
                search_e = ttk.Entry(sf, textvariable=search_v, width=34)
                search_e.pack(side="left", padx=6)
                search_e.focus()

                suggest_lb = tk.Listbox(dlg, height=5, font=("Consolas", 9))
                suggest_lb.pack(fill="x", padx=12)

                def update_suggestions(*_):
                    q = search_v.get().strip().lower()
                    suggest_lb.delete(0, "end")
                    if not q:
                        return
                    for n in all_stat_names:
                        if q in n.lower():
                            suggest_lb.insert("end", n)

                search_v.trace_add("write", update_suggestions)

                ttk.Separator(dlg, orient="horizontal").pack(fill="x", padx=12, pady=6)
                ttk.Label(dlg, text="Eklenenler:" + (" (her 2 mod bir çift oluşturur)" if mode_pair else ""),
                          font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12)
                added_lb = tk.Listbox(dlg, height=6, font=("Consolas", 9))
                added_lb.pack(fill="both", expand=True, padx=12, pady=(2, 4))

                def refresh_added_lb():
                    added_lb.delete(0, "end")
                    if mode_pair:
                        for pair in result_items:
                            added_lb.insert("end", "  +  ".join(pair))
                        if pair_buffer:
                            added_lb.insert("end", f"  → {pair_buffer[0]}  [ikinci bekleniyor...]")
                    else:
                        for item in result_items:
                            added_lb.insert("end", item)

                def add_selected(event=None):
                    sel = suggest_lb.curselection()
                    if not sel:
                        if suggest_lb.size() == 1:
                            name = suggest_lb.get(0)
                        else:
                            return
                    else:
                        name = suggest_lb.get(sel[0])
                    formatted = fmt_effect(name)
                    if mode_pair:
                        pair_buffer.append(formatted)
                        if len(pair_buffer) == 2:
                            result_items.append(list(pair_buffer))
                            pair_buffer.clear()
                    else:
                        if formatted not in result_items:
                            result_items.append(formatted)
                    search_v.set("")
                    suggest_lb.delete(0, "end")
                    refresh_added_lb()

                def remove_last():
                    if mode_pair and pair_buffer:
                        pair_buffer.clear()
                    elif result_items:
                        result_items.pop()
                    refresh_added_lb()

                suggest_lb.bind("<Double-Button-1>", add_selected)
                suggest_lb.bind("<Return>", add_selected)
                search_e.bind("<Return>", add_selected)

                bf = ttk.Frame(dlg)
                bf.pack(fill="x", padx=12, pady=(0, 8))
                ttk.Button(bf, text="Ekle ←", command=add_selected, width=10).pack(side="left", padx=(0, 4))
                ttk.Button(bf, text="Son Sil", command=remove_last, width=10).pack(side="left", padx=(0, 4))
                ttk.Button(bf, text="Geç →", command=dlg.destroy, width=10).pack(side="right", padx=(4, 0))

                def on_confirm():
                    dlg.destroy()

                ttk.Button(bf, text="Tamam ✓", command=on_confirm, width=10).pack(side="right")

                if mode_pair or show_oto:
                    oto_btn = ttk.Button(bf, text="Oto Hesapla", width=12)
                    oto_btn.pack(side="left", padx=(8, 0))
                    status_lbl = ttk.Label(bf, text="")
                    status_lbl.pack(side="left", padx=(4, 0))

                    FRAC_TO_MOD_MAX = {
                        "35% Effect":       "[P][1] Added Small Passive Skills have #% increased Effect(35)",
                        "increased Damage": "[P][1] Added Small Passive Skills also grant: #% increased Damage(4)",
                        "Maximum ES":       "[P][1] Added Small Passive Skills also grant: +# to Maximum Energy Shield(12)",
                        "Maximum Life":     "[P][1] Added Small Passive Skills also grant: +# to Maximum Life(10)",
                        "Maximum Mana":     "[P][1] Added Small Passive Skills also grant: +# to Maximum Mana(10)",
                        "Armour":           "[P][1] Added Small Passive Skills also grant: +# to Armour(40)",
                        "Evasion":          "[P][1] Added Small Passive Skills also grant: +# to Evasion(40)",
                        "All Attributes":   "[S][1] Added Small Passive Skills also grant: +# to All Attributes(4)",
                        "Dexterity":        "[S][1] Added Small Passive Skills also grant: +# to Dexterity(8)",
                        "Strength":         "[S][1] Added Small Passive Skills also grant: +# to Strength(8)",
                        "Intelligence":     "[S][1] Added Small Passive Skills also grant: +# to Intelligence(8)",
                        "all Ele Res":      "[S][1] Added Small Passive Skills also grant: +#% to all Elemental Resistances(4)",
                        "Chaos Res":        "[S][1] Added Small Passive Skills also grant: +#% to Chaos Resistance(5)",
                        "Fire Res":         "[S][1] Added Small Passive Skills also grant: +#% to Fire Resistance(7)",
                        "Cold Res":         "[S][1] Added Small Passive Skills also grant: +#% to Cold Resistance(7)",
                        "Lightning Res":    "[S][1] Added Small Passive Skills also grant: +#% to Lightning Resistance(7)",
                        "Cast Speed":       "[S][1] Added Small Passive Skills also grant: #% increased Cast Speed(3)",
                        "Mana Regen":       "[S][1] Added Small Passive Skills also grant: #% increased Mana Regeneration Rate(6)",
                        "Life Regen":       "[S][1] Added Small Passive Skills also grant: Regenerate #% of Life per Second(0.2)",
                    }
                    FRAC_TO_MOD_MIN = {
                        "35% Effect":       "[P][1] Added Small Passive Skills have #% increased Effect(35)",
                        "increased Damage": "[P][1] Added Small Passive Skills also grant: #% increased Damage(4)",
                        "Maximum ES":       "[P][1] Added Small Passive Skills also grant: +# to Maximum Energy Shield(10)",
                        "Maximum Life":     "[P][1] Added Small Passive Skills also grant: +# to Maximum Life(8)",
                        "Maximum Mana":     "[P][1] Added Small Passive Skills also grant: +# to Maximum Mana(9)",
                        "Armour":           "[P][1] Added Small Passive Skills also grant: +# to Armour(31)",
                        "Evasion":          "[P][1] Added Small Passive Skills also grant: +# to Evasion(31)",
                        "All Attributes":   "[S][1] Added Small Passive Skills also grant: +# to All Attributes(4)",
                        "Dexterity":        "[S][1] Added Small Passive Skills also grant: +# to Dexterity(6)",
                        "Strength":         "[S][1] Added Small Passive Skills also grant: +# to Strength(6)",
                        "Intelligence":     "[S][1] Added Small Passive Skills also grant: +# to Intelligence(6)",
                        "all Ele Res":      "[S][1] Added Small Passive Skills also grant: +#% to all Elemental Resistances(4)",
                        "Chaos Res":        "[S][1] Added Small Passive Skills also grant: +#% to Chaos Resistance(5)",
                        "Fire Res":         "[S][1] Added Small Passive Skills also grant: +#% to Fire Resistance(6)",
                        "Cold Res":         "[S][1] Added Small Passive Skills also grant: +#% to Cold Resistance(6)",
                        "Lightning Res":    "[S][1] Added Small Passive Skills also grant: +#% to Lightning Resistance(6)",
                        "Cast Speed":       "[S][1] Added Small Passive Skills also grant: #% increased Cast Speed(3)",
                        "Mana Regen":       "[S][1] Added Small Passive Skills also grant: #% increased Mana Regeneration Rate(6)",
                        "Life Regen":       "[S][1] Added Small Passive Skills also grant: Regenerate #% of Life per Second(0.2)",
                    }

                    def _oto_hesapla():
                        cluster_name = self.cluster_var.get().strip()
                        if not cluster_name:
                            status_lbl.config(text="⚠️ Cluster seçili değil")
                            return
                        opt_id = find_cluster_option_id(self.stats, cluster_name)
                        if opt_id is None:
                            status_lbl.config(text="⚠️ Option ID bulunamadı")
                            return
                        league_id = self.league_var.get().strip()
                        if not league_id:
                            status_lbl.config(text="⚠️ League seçili değil")
                            return
                        FRAC_STATS = [
                            ("35% Effect",       "fractured.stat_2618549697", 35),
                            ("increased Damage", "fractured.stat_1719521705", 4),
                            ("Maximum ES",       "fractured.stat_2643685329", 12),
                            ("Maximum Life",     "fractured.stat_3819827377", 10),
                            ("Maximum Mana",     "fractured.stat_3994193163", 10),
                            ("Armour",           "fractured.stat_2554466725", 40),
                            ("Evasion",          "fractured.stat_4100161067", 40),
                            ("All Attributes",   "fractured.stat_4036575250", 4),
                            ("Dexterity",        "fractured.stat_2090413987", 8),
                            ("Strength",         "fractured.stat_3258414199", 8),
                            ("Intelligence",     "fractured.stat_724930776",  8),
                            ("all Ele Res",      "fractured.stat_2669029667", 4),
                            ("Chaos Res",        "fractured.stat_1811604576", 5),
                            ("Fire Res",         "fractured.stat_1790411851", 7),
                            ("Cold Res",         "fractured.stat_2709692542", 7),
                            ("Lightning Res",    "fractured.stat_2250780084", 7),
                            ("Cast Speed",       "fractured.stat_1195353227", 3),
                            ("Mana Regen",       "fractured.stat_2474836297", 6),
                            ("Life Regen",       "fractured.stat_3721672021", 0.2),
                        ]
                        rates = self._rates if hasattr(self, "_rates") and self._rates else {"chaos": 1.0, "divine": 200.0}
                        oto_btn.config(state="disabled", text="Aranıyor...")
                        status_lbl.config(text="⏳ Fiyatlar çekiliyor...")
                        dlg.update()

                        def _do():
                            stat_prices = []
                            for name, frac_id, min_roll in FRAC_STATS:
                                body = {
                                    "query": {
                                        "filters": {"misc_filters": {"filters": {"corrupted": {"option": "false"}}}},
                                        "stats": [
                                            {"filters": [{"disabled": False, "id": frac_id, "value": {"min": min_roll}}], "type": "and"},
                                            {"filters": [
                                                {"disabled": False, "id": "enchant.stat_3086156145", "value": {"max": 12, "min": 12}},
                                                build_cluster_base_filter(opt_id)
                                            ], "type": "and"}
                                        ],
                                        "status": {"option": "securable"}
                                    },
                                    "sort": {"price": "asc"}
                                }
                                try:
                                    req = get_next_requester()
                                    search = req.send_request(f"{POE_TRADE_BASE}/search/{league_id}", data=body)
                                    if not search:
                                        stat_prices.append((name, 0.0))
                                        continue
                                    total = int(search.get("total", 0))
                                    ids = search.get("result", [])[:5]
                                    if total <= 0 or not ids:
                                        stat_prices.append((name, 0.0))
                                        continue
                                    qid = search.get("id")
                                    joined = ",".join(ids)
                                    fetch_url = f"{POE_TRADE_BASE}/fetch/{joined}?query={qid}"
                                    fetch = req.send_request(fetch_url, is_fetch=True)
                                    listings = fetch.get("result", []) if fetch else []
                                    prices = []
                                    for r in listings:
                                        try:
                                            li = r["listing"]["price"]
                                            chaos = float(li["amount"]) * rates.get(li["currency"].lower(), 1.0)
                                            if chaos > 0:
                                                prices.append(chaos)
                                        except Exception:
                                            continue
                                    cheapest = min(prices) if prices else 0.0
                                    stat_prices.append((name, cheapest))
                                except Exception:
                                    stat_prices.append((name, 0.0))

                            stat_prices.sort(key=lambda x: x[1], reverse=True)
                            top7 = [name for name, price in stat_prices[:7] if price > 0]
                            mod_map = FRAC_TO_MOD_MAX if mode_pair else FRAC_TO_MOD_MIN

                            def _update_ui():
                                result_items.clear()
                                pair_buffer.clear()
                                if mode_pair:
                                    for i in range(len(top7)):
                                        for j in range(i+1, len(top7)):
                                            m1 = mod_map.get(top7[i])
                                            m2 = mod_map.get(top7[j])
                                            if m1 and m2:
                                                result_items.append([m1, m2])
                                    refresh_added_lb()
                                    oto_btn.config(state="normal", text="Oto Hesapla")
                                    status_lbl.config(text=f"\u2705 {len(top7)} base, {len(result_items)} \u00e7ift eklendi")
                                else:
                                    for name in top7:
                                        m = mod_map.get(name)
                                        if m and m not in result_items:
                                            result_items.append(m)
                                    refresh_added_lb()
                                    oto_btn.config(state="normal", text="Oto Hesapla")
                                    status_lbl.config(text=f"\u2705 {len(top7)} mod eklendi")

                            dlg.after(0, _update_ui)

                        import threading as _th
                        _th.Thread(target=_do, daemon=True).start()

                    oto_btn.config(command=_oto_hesapla)
                dlg.wait_window()
                if cancelled[0]:
                    return None
                return result_items

            stop_pairs = run_effect_wizard_step(
                title="İkili Durdurma (stop_on_two_match)",
                description="Programın durmasını istediğin 2'li mod var mı?\nVarsa ekle, yoksa 'Geç →' de.",
                mode_pair=True
            )
            if stop_pairs is None:
                return

            annul_list = run_effect_wizard_step(
                title="Annulment Koruma (annul_combs)",
                description="Program annulment atarken aşağıdaki modlardan biri kesin olsun dediklerini ekle.\nYoksa 'Geç →' de.",
                mode_pair=False
            )
            if annul_list is None:
                return

            solo_list = run_effect_wizard_step(
                title="Tek Başına Regal (solo_regal_mods)",
                description="Program item maviyken 2. modu bulamasa bile regal denesin dediğin modları ekle.\nYoksa 'Geç →' de.",
                mode_pair=False,
                show_oto=True
            )
            if solo_list is None:
                return

            no_regal_list = run_effect_wizard_step(
                title="Regal ile Arama (no_regal_mods)",
                description="Regalle bulmak istemediğin, alterle bulunmasını istediğin modları ekle.\nYoksa 'Geç →' de.",
                mode_pair=False
            )
            if no_regal_list is None:
                return

            # comb_craft_data oluştur
            comb_dict = {}
            combo_prices = {}
            for idx, vals in enumerate(filtered, start=1):
                parts = [p.strip() for p in vals[1].split("+")]
                mods = ["[P][1] Added Small Passive Skills have #% increased Effect(35)"]
                for p in parts:
                    mods.append(fmt(p))
                key = str(idx)
                comb_dict[key] = mods
                try:
                    combo_prices[key] = {
                        "min_chaos": float(vals[2]),
                        "max_chaos": float(vals[3]),
                        "avg_chaos": float(vals[4]),
                        "listings": int(vals[5]),
                        "trade_url": vals[8],
                    }
                except (TypeError, ValueError, IndexError):
                    pass

            cluster_name = self.cluster_var.get().strip()
            label = self._safe_cluster_name(cluster_name or "effect35")
            ts = time.strftime("%d-%m_%H.%M")

            template = {
                "craft_logic": "Rare (regal)",
                "augment_mode": "Always use",
                "use_exalt": True,
                "use_annul": True,
                "chain_craft": False,
                "chain_count": 1,
                "comb_craft_data": comb_dict,
                "combo_prices": combo_prices,
                "price_meta": {
                    "league": self.league_id,
                    "scanned_at": datetime.now(timezone.utc).isoformat(),
                    "currency": "chaos",
                    "range_basis": "first 10 cheapest listings",
                },
                "stop_on_two_match": stop_pairs,
                "annul_combs": annul_list,
                "solo_regal_mods": solo_list,
                "no_regal_mods": no_regal_list
            }

            itemcraft_dir = os.path.join(BASE_DIR, "itemcraft")
            os.makedirs(itemcraft_dir, exist_ok=True)
            fname = os.path.join(itemcraft_dir, f"%35_{label}_{ts}.json")
            with open(fname, "w", encoding="utf-8") as f:
                _json.dump(template, f, ensure_ascii=False, indent=2)

            self._log(f"[✅] Effect template kaydedildi: %35_{label}_{ts}.json ({len(filtered)} kombinasyon)")
        except Exception as e:
            self._log(f"[Hata] Effect template export: {e}")


    def _scan_fractured_bases(self):
        """Seçili cluster tipinde tüm small passive stat tier1 max roll fractured baselerini tarar ve tabloya yazar."""
        try:
            cluster_name = self.cluster_var.get().strip()
            if not cluster_name:
                self._log("[⚠️] Önce cluster tipi seçin.")
                return
            opt_id = find_cluster_option_id(self.stats, cluster_name)
            if opt_id is None:
                self._log(f"[⚠️] '{cluster_name}' için option ID bulunamadı.")
                return
            league_id = self.league_var.get().strip()
            if not league_id:
                self._log("[⚠️] Önce league seçin.")
                return

            FRAC_STATS = [
                ("35% Effect",       "fractured.stat_2618549697", 35),
                ("increased Damage", "fractured.stat_1719521705", 4),
                ("Maximum ES",       "fractured.stat_2643685329", 12),
                ("Maximum Life",     "fractured.stat_3819827377", 10),
                ("Maximum Mana",     "fractured.stat_3994193163", 10),
                ("Armour",           "fractured.stat_2554466725", 40),
                ("Evasion",          "fractured.stat_4100161067", 40),
                ("All Attributes",   "fractured.stat_4036575250", 4),
                ("Dexterity",        "fractured.stat_2090413987", 8),
                ("Strength",         "fractured.stat_3258414199", 8),
                ("Intelligence",     "fractured.stat_724930776",  8),
                ("all Ele Res",      "fractured.stat_2669029667", 4),
                ("Chaos Res",        "fractured.stat_1811604576", 5),
                ("Fire Res",         "fractured.stat_1790411851", 7),
                ("Cold Res",         "fractured.stat_2709692542", 7),
                ("Lightning Res",    "fractured.stat_2250780084", 7),
                ("Cast Speed",       "fractured.stat_1195353227", 3),
                ("Mana Regen",       "fractured.stat_2474836297", 6),
                ("Life Regen",       "fractured.stat_3721672021", 0.2),
            ]

            rates = self._rates if hasattr(self, "_rates") and self._rates else {"chaos": 1.0, "divine": 200.0}
            self._log(f"[🔍] Fractured base tarama başlıyor — {cluster_name}...")

            # Tabloyu temizle
            for iid in self.tree.get_children():
                self.tree.delete(iid)

            def _do_scan():
                for name, frac_id, min_roll in FRAC_STATS:
                    body = {
                        "query": {
                            "filters": {
                                "misc_filters": {"filters": {"corrupted": {"option": "false"}}}
                            },
                            "stats": [
                                {"filters": [{"disabled": False, "id": frac_id, "value": {"min": min_roll}}], "type": "and"},
                                {"filters": [
                                    {"disabled": False, "id": "enchant.stat_3086156145", "value": {"max": 12, "min": 12}},
                                    build_cluster_base_filter(opt_id)
                                ], "type": "and"}
                            ],
                            "status": {"option": "securable"}
                        },
                        "sort": {"price": "asc"}
                    }
                    try:
                        req = get_next_requester()
                        search = req.send_request(f"{POE_TRADE_BASE}/search/{league_id}", data=body)
                        if not search:
                            self.after(0, lambda n=name: self._log(f"  [⚠️] {n}: sonuç yok"))
                            continue

                        total = int(search.get("total", 0))
                        qid = search.get("id")
                        ids = search.get("result", [])[:10]
                        link = f"https://www.pathofexile.com/trade/search/{league_id}/{qid}"

                        if total <= 0 or not ids:
                            def _add_empty(n=name, t=total, lk=link):
                                self.tree.insert("", "end", values=("", n, "—", "—", "—", str(t), "—", "—", lk))
                            self.after(0, _add_empty)
                            continue

                        joined = ",".join(ids)
                        fetch_url = f"{POE_TRADE_BASE}/fetch/{quote(joined)}?query={quote(qid)}"
                        fetch = req.send_request(fetch_url, is_fetch=True)
                        listings = fetch.get("result", []) if fetch else []

                        prices, ages = [], []
                        for r in listings:
                            try:
                                li = r["listing"]["price"]
                                chaos = float(li["amount"]) * rates.get(li["currency"].lower(), 1.0)
                                if chaos > 0:
                                    prices.append(chaos)
                                    ages.append(_format_age(r["listing"]["indexed"]))
                            except Exception:
                                continue

                        cheapest = min(prices) if prices else 0.0
                        max10 = max(prices) if prices else 0.0
                        avg10 = sum(prices) / len(prices) if prices else 0.0

                        def _avg_age(age_list):
                            vals = []
                            for a in age_list:
                                if a.endswith("m"): vals.append(int(a[:-1]) / 60)
                                elif a.endswith("h"): vals.append(int(a[:-1]))
                                elif a.endswith("d"): vals.append(int(a[:-1]) * 24)
                            if not vals: return "?"
                            avg_h = sum(vals) / len(vals)
                            if avg_h < 1: return f"{int(avg_h*60)}m"
                            if avg_h < 24: return f"{int(avg_h)}h"
                            return f"{int(avg_h/24)}d"

                        age_cheap = ages[prices.index(min(prices))] if prices else "?"
                        age_avg = _avg_age(ages)

                        cheapest_str = f"{cheapest:.0f}c" if cheapest > 0 else "—"
                        max_str = f"{max10:.0f}c" if max10 > 0 else "—"
                        avg_str = f"{avg10:.0f}c" if avg10 > 0 else "—"

                        def _add_row(n=name, cs=cheapest_str, mx=max_str, av=avg_str, t=total, ac=age_cheap, aa=age_avg, lk=link):
                            self.tree.insert("", "end", values=("", n, cs, mx, av, str(t), ac, aa, lk))
                            self._log(f"  {n}: {cs} ({t} ilan)")
                        self.after(0, _add_row)

                    except Exception as ex:
                        self.after(0, lambda n=name, e=str(ex): self._log(f"  [Hata] {n}: {e}"))

                self.after(0, lambda: self._log("[✅] Fractured base tarama tamamlandı."))

            import threading as _th
            _th.Thread(target=_do_scan, daemon=True).start()

        except Exception as e:
            self._log(f"[Hata] Fractured base tarama: {e}")

    def _get_selected_effect_stats(self):
        """Tiklenmiş effect stat'larını (stat_id, min_val, side) listesi olarak döner."""
        result = []
        for name, stat_id, default, side, _ in SMALL_PASSIVE_STATS:
            chk_var, min_var = self._effect_checks[stat_id]
            if chk_var.get():
                try:
                    min_val = int(min_var.get())
                except Exception:
                    min_val = default
                result.append((stat_id, min_val, side))
        return result

    # --- Sorting helpers ---
    def _age_to_minutes(self, s: str) -> float:
        """'45m'/'3h'/'2d' → dakika (sıralama için). '?' çok büyük olsun."""
        if not s or s == "?":
            return 10**12
        try:
            if s.endswith("m"):
                return int(s[:-1])
            if s.endswith("h"):
                return int(s[:-1]) * 60
            if s.endswith("d"):
                return int(s[:-1]) * 1440
        except Exception:
            return 10**12
        return 10**12

    def _col_type(self, col: str):
        """Sütun tipini belirle: 'num' | 'age' | 'str' """
        if col in ("cheapest_chaos", "max_chaos", "avg_chaos", "listings"):
            return "num"
        if col in ("age_cheapest", "age_avg10"):
            return "age"
        return "str"

    def _sort_tree(self, col, reverse=False):
        """CSV import sonrasında da çalışan genel sıralama."""
        ctype = self._col_type(col)
        rows = []
        for iid in self.tree.get_children(""):
            val = self.tree.set(iid, col)
            if ctype == "num":
                try:
                    key = float(val.replace("c", "").replace("d", "").replace("—", "").strip())
                except Exception:
                    key = float("inf")
            elif ctype == "age":
                key = self._age_to_minutes(val)
            else:
                key = val
            rows.append((key, iid))

        rows.sort(reverse=reverse)
        for idx, (_, iid) in enumerate(rows):
            self.tree.move(iid, "", idx)

        # toggling
        self.tree.heading(col, command=lambda: self._sort_tree(col, not reverse))

    # --- Bootstrap ---
    def _reload_everything(self):
        self.btn_start.config(state="disabled")
        self.btn_refresh.config(state="disabled")
        self._log("[İş] Yeniden yükleniyor...")
        threading.Thread(target=self._bootstrap_worker, daemon=True).start()

    def _bootstrap_worker(self):
        try:
            reload_requesters(log_fn=self._log)
            league_id = get_current_challenge_league_id()
            self.league_id = league_id
            self.league_var.set(league_id)

            self.stats = load_or_fetch_stats()
            self.rates = get_currency_rates_chaos(league_id)
            self.clusters = load_clusters_with_ids()

            names = [c["clusterName"] for c in self.clusters]
            self.cluster_combo["values"] = names
            if names:
                self.cluster_combo.current(0)

            self._effect_stat_id = find_effect_stat_id(self.stats)
            self.btn_start.config(state="normal")
            self.btn_refresh.config(state="normal")
            self._log("[Hazır] Cluster listesi yüklendi.")
        except Exception as e:
            self._log(f"[Hata] Bootstrap: {e}")

    # --- Log ---
    def _log(self, msg: str):
        try:
            self.log.insert("end", msg + "\n")
            self.log.see("end")
        except Exception:
            safe = msg.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
            self.log.insert("end", safe + "\n")
            self.log.see("end")

    # --- Table helpers ---
    def _append_result(
        self,
        combo_text,
        cheapest,
        max_price,
        avg_price,
        listings,
        age_cheapest,
        age_avg10,
        link,
    ):
        row = (
            "",  # checkbox boş
            combo_text,
            f"{cheapest:.1f}",
            f"{max_price:.1f}",
            f"{avg_price:.1f}",
            str(listings),
            age_cheapest or "?",
            age_avg10 or "?",
            link or "",
        )
        self.tree.insert("", "end", values=row)
        self._all_rows_cache.append(row)

    def _on_tree_double_click_link_only(self, event):
        # Sadece "link" sütunu (#8) çift tıklanınca aç
        col = self.tree.identify_column(event.x)  # '#1', '#2', ...
        if col != f"#{len(self.columns)}":
            return
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        values = self.tree.item(row_id, "values")
        if len(values) < len(self.columns):
            return
        link = values[-1]
        if isinstance(link, str) and link.startswith("http"):
            webbrowser.open(link)

    def _on_click_maybe_toggle_checkbox(self, event):
        # Checkbox sütununa tıklanırsa işaretle/çıkar
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self.tree.identify_column(event.x)
        if col != "#1":  # first column = checkbox
            return
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        vals = list(self.tree.item(row_id, "values"))
        vals[0] = "" if vals[0] == "✓" else "✓"
        self.tree.item(row_id, values=tuple(vals))

        # cache'i de güncelle
        idx = self._row_index_in_cache(row_id)
        if idx is not None:
            cache_vals = list(self._all_rows_cache[idx])
            cache_vals[0] = vals[0]
            self._all_rows_cache[idx] = tuple(cache_vals)

    def _row_index_in_cache(self, row_id):
        # satırın textine göre kaba bir eşleme; güvenli olması için combination + link karşılaştıracağız
        vals = self.tree.item(row_id, "values")
        if not vals:
            return None
        combo, link = vals[1], vals[-1]
        for i, r in enumerate(self._all_rows_cache):
            if r[1] == combo and r[-1] == link:
                return i
        return None

    # --- Pause / Stop ---
    def toggle_pause(self):
        self.paused = not self.paused
        self.btn_pause.config(text="▶ Devam Et" if self.paused else "⏸ Duraklat")
        if not self.paused:
            self._log("[Devam Ediyor] Arama sürdürüldü.")

    def _stop_search(self):
        self._stop_flag = True
        self.paused = False
        self.btn_pause.config(text="⏸ Duraklat")
        self._log("[DURDUR] Akım iş durduruldu.")

    # --- CSV Export / Import ---
    def _safe_cluster_name(self, s: str) -> str:
        # Dosya adı güvenliği
        s = s.strip()
        s = re.sub(r"[\\/:*?\"<>|]", "_", s)
        s = re.sub(r"\s+", " ", s)
        return s

    def _export_csv(self):
        try:
            # Seçili varsa sadece seçilileri, yoksa tümünü al
            rows_tree = []
            for iid in self.tree.get_children():
                v = self.tree.item(iid, "values")
                if v and (v[0] == "✓" or not any(self.tree.item(i, "values")[0] == "✓" for i in self.tree.get_children())):
                    rows_tree.append(v)

            if not rows_tree:
                self._log("[⚠️] Kayıt bulunamadı, CSV boş.")
                return

            # Checkbox'ı yazma (kolon 0)
            rows = [r[1:] for r in rows_tree]

            cluster = self._safe_cluster_name(self.cluster_var.get() or "results")
            ts = time.strftime("%H-%d-%m")  # saat-gün-ay
            fname = f"results_{cluster}_{ts}.csv"

            with open(fname, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Kombinasyon",
                    "En Ucuz (chaos)",
                    "Ilk 10 Maksimum (chaos)",
                    "Ortalama (chaos)",
                    "İlan",
                    "Yaş (en ucuz)",
                    "Yaş (ilk 10 ort.)",
                    "Link"
                ])
                for r in rows:
                    writer.writerow(r[0:8])

            self._log(f"[✅] {fname} kaydedildi ({len(rows)} satır).")
        except Exception as e:
            self._log(f"[Hata] CSV kaydedilemedi: {e}")

    def _export_template(self):
        try:
            all_iids = list(self.tree.get_children())
            if not all_iids:
                self._log("[⚠️] Tabloda veri yok.")
                return

            # ── ADIM 1: Mod seçimi ──────────────────────────────────────────
            mode_dialog = tk.Toplevel(self)
            mode_dialog.title("Template Export")
            mode_dialog.geometry("320x170")
            mode_dialog.resizable(False, False)
            mode_dialog.grab_set()
            ttk.Label(mode_dialog, text="Hangi kombinasyonları dahil etmek istiyorsun?",
                      wraplength=290).pack(pady=(14, 10))
            mode = [None]

            def pick(m):
                mode[0] = m
                mode_dialog.destroy()

            bf0 = ttk.Frame(mode_dialog)
            bf0.pack()
            ttk.Button(bf0, text="✓ Sadece Tikliler",            width=26, command=lambda: pick("checked")).pack(pady=3)
            ttk.Button(bf0, text="💰 Sadece Fiyata Göre",        width=26, command=lambda: pick("price")).pack(pady=3)
            ttk.Button(bf0, text="✓+💰 Hem Tikliler Hem Fiyat", width=26, command=lambda: pick("both")).pack(pady=3)
            mode_dialog.wait_window()
            if mode[0] is None:
                return

            # ── ADIM 2: Chaos eşiği (fiyat modu varsa) ─────────────────────
            threshold = None
            if mode[0] in ("price", "both"):
                pd2 = tk.Toplevel(self)
                pd2.title("Chaos Eşiği")
                pd2.geometry("300x110")
                pd2.resizable(False, False)
                pd2.grab_set()
                ttk.Label(pd2, text="Minimum 'En Ucuz' chaos değeri girin:").pack(pady=(16, 4))
                tvar = tk.StringVar(value="300")
                ent2 = ttk.Entry(pd2, textvariable=tvar, width=16, justify="center")
                ent2.pack()
                ent2.focus()
                conf2 = [False]

                def ok2(e=None):
                    conf2[0] = True
                    pd2.destroy()

                bf2 = ttk.Frame(pd2)
                bf2.pack(pady=8)
                ttk.Button(bf2, text="Tamam", command=ok2,          width=10).pack(side="left", padx=4)
                ttk.Button(bf2, text="İptal", command=pd2.destroy,  width=10).pack(side="left", padx=4)
                ent2.bind("<Return>", ok2)
                pd2.wait_window()
                if not conf2[0]:
                    return
                try:
                    threshold = float(tvar.get().strip())
                except ValueError:
                    self._log("[⚠️] Geçersiz sayı.")
                    return

            # ── Kombinasyonları topla ────────────────────────────────────────
            seen_combos = set()
            filtered = []

            def add_row(vals):
                key = vals[1]
                if key not in seen_combos:
                    seen_combos.add(key)
                    filtered.append(vals)

            if mode[0] in ("checked", "both"):
                for iid in all_iids:
                    vals = self.tree.item(iid, "values")
                    if vals and vals[0] == "✓":
                        add_row(vals)

            if mode[0] in ("price", "both"):
                for iid in all_iids:
                    vals = self.tree.item(iid, "values")
                    if not vals or len(vals) < 3:
                        continue
                    try:
                        if float(vals[2]) >= threshold:
                            add_row(vals)
                    except (ValueError, IndexError):
                        continue

            if not filtered:
                self._log("[⚠️] Seçilen kriterlere uyan kombinasyon bulunamadı.")
                return

            # ── Notable side lookup ──────────────────────────────────────────
            cluster_name = self.cluster_var.get().strip()
            cluster = find_cluster_by_name(self.clusters, cluster_name) if self.clusters and cluster_name else None

            # Cluster'daki tüm notable isimlerini topla (arama için)
            all_notables = []
            if cluster:
                all_notables = cluster.get("notables", [])

            def get_side(notable_name):
                for n in all_notables:
                    if n["notableName"].strip().lower() == notable_name.strip().lower():
                        return "S" if n.get("side", "").lower() == "suffix" else "P"
                return "P"

            def fmt(name):
                return f"[{get_side(name)}][1] 1 Added Passive Skill is {name}"

            # ── WIZARD: 4 soruluk yardımcı fonksiyon ────────────────────────
            def run_wizard_step(title, description, mode_pair=False):
                """
                Affix arama + liste içeren wizard adımı.
                mode_pair=True → ikili çift toplar (stop_on_two_match)
                mode_pair=False → tekli notable listesi
                Geri dönüş: liste (iptal edilirse None)
                """
                result_items = []   # ikili modda: [[a,b], ...], tekli modda: [str, ...]
                pair_buffer  = []   # ikili mod için geçici tampon
                cancelled    = [False]

                dlg = tk.Toplevel(self)
                dlg.title(title)
                dlg.geometry("520x420")
                dlg.resizable(True, True)
                dlg.grab_set()

                # Açıklama
                ttk.Label(dlg, text=description, wraplength=490,
                          justify="left").pack(fill="x", padx=12, pady=(12, 6))

                # Arama çerçevesi
                sf = ttk.Frame(dlg)
                sf.pack(fill="x", padx=12, pady=(0, 4))
                ttk.Label(sf, text="Affix Ara:").pack(side="left")
                search_v = tk.StringVar()
                search_e = ttk.Entry(sf, textvariable=search_v, width=34)
                search_e.pack(side="left", padx=6)
                search_e.focus()

                # Öneri listesi
                suggest_lb = tk.Listbox(dlg, height=5, font=("Consolas", 9))
                suggest_lb.pack(fill="x", padx=12)

                def update_suggestions(*_):
                    q = search_v.get().strip().lower()
                    suggest_lb.delete(0, "end")
                    if not q:
                        return
                    for n in all_notables:
                        nm = n["notableName"]
                        if q in nm.lower():
                            suggest_lb.insert("end", nm)

                search_v.trace_add("write", update_suggestions)

                # Eklenen notable'lar (gösterim)
                ttk.Separator(dlg, orient="horizontal").pack(fill="x", padx=12, pady=6)
                ttk.Label(dlg, text="Eklenenler:" + (" (her 2 notable bir çift oluşturur)" if mode_pair else ""),
                          font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12)
                added_lb = tk.Listbox(dlg, height=6, font=("Consolas", 9))
                added_lb.pack(fill="both", expand=True, padx=12, pady=(2, 4))

                def refresh_added_lb():
                    added_lb.delete(0, "end")
                    if mode_pair:
                        for pair in result_items:
                            added_lb.insert("end", "  +  ".join(pair))
                        # tampondaki yarım çift
                        if pair_buffer:
                            added_lb.insert("end", f"  → {pair_buffer[0]}  [ikinci bekleniyor...]")
                    else:
                        for item in result_items:
                            added_lb.insert("end", item)

                def add_selected(event=None):
                    sel = suggest_lb.curselection()
                    if not sel:
                        # Enter'a basıldıysa ve tek eşleşme varsa onu al
                        if suggest_lb.size() == 1:
                            name = suggest_lb.get(0)
                        else:
                            return
                    else:
                        name = suggest_lb.get(sel[0])

                    formatted = fmt(name)

                    if mode_pair:
                        if not pair_buffer:
                            pair_buffer.append(formatted)
                        else:
                            if formatted != pair_buffer[0]:
                                result_items.append([pair_buffer[0], formatted])
                                pair_buffer.clear()
                            else:
                                pair_buffer.clear()  # aynı notable iki kez → iptal
                    else:
                        if formatted not in result_items:
                            result_items.append(formatted)

                    search_v.set("")
                    suggest_lb.delete(0, "end")
                    refresh_added_lb()

                def remove_last():
                    if mode_pair:
                        if pair_buffer:
                            pair_buffer.clear()
                        elif result_items:
                            result_items.pop()
                    else:
                        if result_items:
                            result_items.pop()
                    refresh_added_lb()

                suggest_lb.bind("<Double-1>", add_selected)
                suggest_lb.bind("<Return>",   add_selected)
                search_e.bind("<Return>",     add_selected)

                # Alt butonlar
                bot = ttk.Frame(dlg)
                bot.pack(fill="x", padx=12, pady=(0, 10))
                ttk.Button(bot, text="← Geri Al", command=remove_last).pack(side="left", padx=(0, 6))

                def finish():
                    dlg.destroy()

                def cancel():
                    cancelled[0] = True
                    dlg.destroy()

                ttk.Button(bot, text="Geç →",   command=finish,  width=12).pack(side="right", padx=(4, 0))
                ttk.Button(bot, text="İptal",   command=cancel,  width=8).pack(side="right")

                dlg.wait_window()
                if cancelled[0]:
                    return None
                return result_items

            # ── ADIM 3a: stop_on_two_match ───────────────────────────────────
            stop_pairs = run_wizard_step(
                title="İkili Durdurma (stop_on_two_match)",
                description=(
                    "Programın durmasını istediğin 2'li notable var mı?\n"
                    "İmprint craft veya fracture için istediğin ikililer varsa ekle, yoksa 'Geç →' de.\n\n"
                    "Eklemek için affix ara → listeden çift tıkla veya Enter. "
                    "Her 2 seçim bir çift oluşturur."
                ),
                mode_pair=True
            )
            if stop_pairs is None:
                return

            # ── ADIM 3b: annul_combs ─────────────────────────────────────────
            annul_list = run_wizard_step(
                title="Annulment Koruma (annul_combs)",
                description=(
                    "Program annulment atarken aşağıdaki modlardan biri kesin olsun dediklerini ekle.\n"
                    "Hiç mod eklenmezse program kombinasyonları tamamlamak için olağan şekilde annulment harcar."
                ),
                mode_pair=False
            )
            if annul_list is None:
                return

            # ── ADIM 3c: solo_regal_mods ─────────────────────────────────────
            solo_list = run_wizard_step(
                title="Tek Başına Regal (solo_regal_mods)",
                description=(
                    "Program item maviyken 2. modu bulamasa bile regal denesin dediğin modları ekle.\n"
                    "Böyle bir mod yoksa 'Geç →' de."
                ),
                mode_pair=False
            )
            if solo_list is None:
                return

            # ── ADIM 3d: no_regal_mods ───────────────────────────────────────
            no_regal_list = run_wizard_step(
                title="Regal ile Arama (no_regal_mods)",
                description=(
                    "Program item maviyken 2 modu buldu, regal atıp 3. modu arayacak.\n"
                    "Aşağıdaki modları regalle bulmam zor. Çok zor geliyor zaten.\n"
                    "Bunları item maviyken alterle bulmalı dediklerini ekle.\n"
                    "(öyle bir mod yoksa 'Geç →' de)"
                ),
                mode_pair=False
            )
            if no_regal_list is None:
                return

            # ── JSON oluştur ─────────────────────────────────────────────────
            import json as _json
            comb_dict = {}
            combo_prices = {}
            for idx, vals in enumerate(filtered, start=1):
                parts = [p.strip() for p in vals[1].split("+")]
                key = str(idx)
                comb_dict[key] = [fmt(p) for p in parts]
                try:
                    combo_prices[key] = {
                        "min_chaos": float(vals[2]),
                        "max_chaos": float(vals[3]),
                        "avg_chaos": float(vals[4]),
                        "listings": int(vals[5]),
                        "trade_url": vals[8],
                    }
                except (TypeError, ValueError, IndexError):
                    pass

            template = {
                "craft_logic": "Rare (regal)",
                "augment_mode": "Always use",
                "use_exalt": True,
                "use_annul": True,
                "chain_craft": False,
                "chain_count": 1,
                "comb_craft_data": comb_dict,
                "combo_prices": combo_prices,
                "price_meta": {
                    "league": self.league_id,
                    "scanned_at": datetime.now(timezone.utc).isoformat(),
                    "currency": "chaos",
                    "range_basis": "first 10 cheapest listings",
                },
                "stop_on_two_match": stop_pairs,
                "annul_combs": annul_list,
                "solo_regal_mods": solo_list,
                "no_regal_mods": no_regal_list
            }
            inner = _json.dumps(template, ensure_ascii=False, indent=2)

            # ── Kaydet ───────────────────────────────────────────────────────
            # Cluster adından kısa etiket üret
            CLUSTER_LABELS = [
                ("Axe Attacks deal",                              "Axe"),
                ("Staff Attacks deal",                            "Staff"),
                ("Claw Attacks deal",                             "Claw"),
                ("increased Damage with Bows",                    "Bow"),
                ("Wand Attacks deal",                             "Wand"),
                ("increased Damage with Two Handed",              "TwoHand"),
                ("increased Attack Damage while Dual Wielding",   "DualWield"),
                ("increased Attack Damage while holding a Shield","Shield"),
                ("increased Attack Damage",                       "Attack"),
                ("increased Spell Damage",                        "Spell"),
                ("increased Elemental Damage",                    "Ele"),
                ("increased Physical Damage",                     "Phys"),
                ("increased Fire Damage",                         "Fire"),
                ("increased Lightning Damage",                    "Light"),
                ("increased Cold Damage",                         "Cold"),
                ("increased Chaos Damage",                        "Chaos"),
                ("Minions deal",                                  "Minion"),
            ]
            label = None
            cn_lower = cluster_name.lower()
            for keyword, short in CLUSTER_LABELS:
                if keyword.lower() in cn_lower:
                    label = short
                    break
            if not label:
                label = self._safe_cluster_name(cluster_name or "results")

            ts = time.strftime("%d-%m_%H.%M")
            default_name = f"{label}_{ts}.json"

            # itemcraft klasörüne otomatik kaydet
            itemcraft_dir = os.path.join(BASE_DIR, "itemcraft")
            os.makedirs(itemcraft_dir, exist_ok=True)
            fname = os.path.join(itemcraft_dir, default_name)

            with open(fname, "w", encoding="utf-8") as f:
                f.write(inner)

            self._log(f"[✅] itemcraft/{default_name} kaydedildi ({len(filtered)} kombinasyon).")
        except Exception as e:
            self._log(f"[Hata] Template export: {e}")

    def _open_proxy_settings(self):
        """Proxy ve POESESSID ayarları penceresi."""
        entries = load_proxy_config()
        # 3 satır için varsayılan boş dict
        while len(entries) < 3:
            entries.append({"ip": "", "port": "", "user": "", "password": "", "poesessid": ""})

        win = tk.Toplevel(self)
        win.title("Proxy / POESESSID Ayarları")
        win.geometry("700x480")
        win.resizable(False, False)
        win.grab_set()

        headers = ["IP", "Port", "Kullanıcı", "Şifre", "POESESSID"]
        col_widths = [18, 7, 14, 16, 38]

        for col, (h, w) in enumerate(zip(headers, col_widths)):
            ttk.Label(win, text=h, font=("Segoe UI", 9, "bold")).grid(row=0, column=col, padx=4, pady=(10,2), sticky="w")

        vars_list = []
        for row_i, e in enumerate(entries[:3], start=1):
            row_vars = []
            for col, (key, w) in enumerate(zip(["ip","port","user","password","poesessid"], col_widths)):
                v = tk.StringVar(value=e.get(key, ""))
                ent = ttk.Entry(win, textvariable=v, width=w)
                if key == "password":
                    ent.config(show="*")
                ent.grid(row=row_i, column=col, padx=4, pady=3)
                row_vars.append((key, v))
            vars_list.append(row_vars)

        ttk.Separator(win, orient="horizontal").grid(row=4, column=0, columnspan=5, sticky="ew", padx=4, pady=6)
        ttk.Label(win, text="Kendi hesabım (proxy yok, kendi IP):",
                  font=("Segoe UI", 9, "bold")).grid(row=5, column=0, columnspan=2, padx=4, sticky="w")
        own_sid_var = tk.StringVar()
        own_entry = next((e for e in entries if not e.get("ip", "").strip()), None)
        if own_entry:
            own_sid_var.set(own_entry.get("poesessid", ""))
        ttk.Label(win, text="POESESSID:").grid(row=5, column=2, padx=4, sticky="e")
        ttk.Entry(win, textvariable=own_sid_var, width=38).grid(row=5, column=3, columnspan=2, padx=4, pady=3, sticky="w")
        ttk.Label(win, text="3 proxy + kendi hesabın = 4x hız.",
                  foreground="gray").grid(row=6, column=0, columnspan=5, padx=4, pady=(2,0), sticky="w")

        def save_and_close():
            new_entries = []
            for row_vars in vars_list:
                d = {k: v.get().strip() for k, v in row_vars}
                if d["ip"] and d["poesessid"]:
                    new_entries.append(d)
            own_sid = own_sid_var.get().strip()
            if own_sid:
                new_entries.append({"ip": "", "port": "", "user": "", "password": "", "poesessid": own_sid})
            save_proxy_config(new_entries)
            reload_requesters(log_fn=self._log)
            active = len(_REQUESTERS)
            self._log(f"[?] Proxy ayarlar? kaydedildi. {active} aktif requester.")
            win.destroy()

        def clear_all():
            for row_vars in vars_list:
                for _, v in row_vars:
                    v.set("")
            own_sid_var.set("")


        # Test sonuç label
        test_result_var = tk.StringVar(value="")
        ttk.Label(win, textvariable=test_result_var, wraplength=680,
                  justify="left", foreground="gray").grid(row=8, column=0, columnspan=5, padx=8, sticky="w")

        def test_proxies():
            test_result_var.set("Test ediliyor...")
            win.update()
            results = []
            for row_vars in vars_list:
                d = {k: v.get().strip() for k, v in row_vars}
                ip = d.get("ip", "")
                if not ip:
                    continue
                try:
                    proxy_url = build_proxy_url(ip, d["port"], d["user"], d["password"])
                    proxies = {"http": proxy_url, "https": proxy_url}
                    sid = d.get("poesessid", "")
                    cookies = {"POESESSID": sid} if sid else {}
                    r = requests.get(
                        "https://www.pathofexile.com/api/trade/data/stats",
                        headers=UA, cookies=cookies, proxies=proxies, timeout=8
                    )
                    if r.status_code == 200:
                        results.append(f"✅ {ip}")
                    else:
                        results.append(f"❌ {ip} (HTTP {r.status_code})")
                except Exception as e:
                    results.append(f"❌ {ip} ({str(e)[:40]})")
            # Kendi IP de test et
            own_sid = own_sid_var.get().strip()
            if own_sid:
                try:
                    r = requests.get(
                        "https://www.pathofexile.com/api/trade/data/stats",
                        headers=UA, cookies={"POESESSID": own_sid}, timeout=8
                    )
                    status = "✅ Kendi IP" if r.status_code == 200 else f"❌ Kendi IP (HTTP {r.status_code})"
                    results.append(status)
                except Exception as e:
                    results.append(f"❌ Kendi IP ({str(e)[:40]})")
            test_result_var.set("  |  ".join(results) if results else "Test edilecek proxy yok.")

        btn_frame = ttk.Frame(win)
        btn_frame.grid(row=9, column=0, columnspan=5, pady=12)
        ttk.Button(btn_frame, text="💾 Kaydet", command=save_and_close, width=12).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="🗑 Temizle", command=clear_all, width=12).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="🔍 Test Et", command=lambda: threading.Thread(target=test_proxies, daemon=True).start(), width=12).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="İptal", command=win.destroy, width=10).pack(side="left", padx=6)

    def _update_notables(self):
        self.btn_update_notables.config(state="disabled")
        self._log("[🔄] Notable güncelleme başladı...")

        def _worker():
            try:
                stats = fetch_trade_stats_cache()
                lookup = build_enchant_lookup(stats)
                clusters = scrape_large_clusters(lookup)
                import json as _j
                os.makedirs(DATA_DIR, exist_ok=True)
                with open(SCRAPER_OUT_FILE, "w", encoding="utf-8") as f:
                    _j.dump(clusters, f, ensure_ascii=False, indent=2)
                self._log(f"[✅] {len(clusters)} cluster güncellendi → data/clusters_with_ids.json")
                missing = sum(1 for c in clusters for n in c["notables"] if not n.get("notableId"))
                if missing:
                    self._log(f"[⚠️] {missing} notable için enchant id bulunamadı.")
                # Cluster listesini yenile
                self._reload_everything()
            except Exception as e:
                self._log(f"[Hata] Notable güncelleme: {e}")
            finally:
                self.btn_update_notables.config(state="normal")

        threading.Thread(target=_worker, daemon=True).start()

    def _import_csv(self):
        try:
            path = filedialog.askopenfilename(
                title="CSV seç",
                filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
            )
            if not path:
                return

            with open(path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                rows = list(reader)

            if not rows:
                self._log("[⚠️] CSV boş.")
                return

            header = rows[0]
            data_rows = rows[1:]

            # Eski CSV (checkbox yok) beklenen sıra:
            # [Kombinasyon, En Ucuz, Ortalama, İlan, Yaş(en ucuz), Yaş(ilk10), Link]
            # Yeni CSV (checkbox'lu yazmıyoruz zaten)
            # Yine de kolon sayısı kontrolü yapalım
            self.tree.delete(*self.tree.get_children())
            self._all_rows_cache.clear()

            for r in data_rows:
                if not r:
                    continue
                # Eski dosya: uzunluğu 7 ise — başına boş checkbox ekle
                if len(r) >= 8:
                    row = ("", r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7])
                elif len(r) >= 7:
                    row = ("", r[0], r[1], r[2], r[2], r[3], r[4], r[5], r[6])
                else:
                    padded = (r + [""] * 8)[:8]
                    row = ("",) + tuple(padded)
                self.tree.insert("", "end", values=row)
                self._all_rows_cache.append(row)

            self._log(f"[📥] {os.path.basename(path)} içe aktarıldı.")
        except Exception as e:
            self._log(f"[Hata] CSV içe aktarılamadı: {e}")

    # --- Filter ---
    def _filter_table(self, event=None):
        """
        'fan+smite' gibi '+' ile AND filtre.
        Her karakter değişiminde tabloyu canlı günceller.
        Boşsa tüm tabloyu geri yükler.
        """
        query = self.search_var.get().strip().lower()
        words = [w for w in query.split("+") if w]

        # Tamamen temizlenmişse tabloyu resetle
        if not words:
              self.tree.delete(*self.tree.get_children())
              for row in self._all_rows_cache:
                 self.tree.insert("", "end", values=row)
              return

        # Filtre aktifse sadece eşleşenleri göster
        self.tree.delete(*self.tree.get_children())
        for row in self._all_rows_cache:
              combo = (row[1] or "").lower()
              if all(w in combo for w in words):
                 self.tree.insert("", "end", values=row)

    # --- Search Flow ---
    def start_search(self):
        if not self.stats or not self.rates or not self.league_id:
            messagebox.showerror("Hata", "Sistem henüz hazır değil.")
            return

        self.btn_start.config(state="disabled")
        self.btn_pause.config(state="normal")
        self.btn_stop.config(state="normal")
        self._stop_flag = False

        self.tree.delete(*self.tree.get_children())
        self._all_rows_cache.clear()

        if self._scan_mode == "effect":
            cluster_name = self.cluster_var.get().strip()
            if not cluster_name:
                messagebox.showwarning("Uyarı", "Lütfen bir Large Cluster base seçin.")
                self.btn_start.config(state="normal")
                self.btn_pause.config(state="disabled")
                self.btn_stop.config(state="disabled")
                return
            selected = self._get_selected_effect_stats()
            if not selected:
                messagebox.showwarning("Uyarı", "En az bir stat seçin.")
                self.btn_start.config(state="normal")
                self.btn_pause.config(state="disabled")
                self.btn_stop.config(state="disabled")
                return
            threading.Thread(target=self._effect_search_worker, args=(cluster_name, selected), daemon=True).start()
        else:
            if not self.clusters:
                messagebox.showerror("Hata", "Cluster listesi henüz yüklenmedi.")
                self.btn_start.config(state="normal")
                self.btn_pause.config(state="disabled")
                self.btn_stop.config(state="disabled")
                return
            cluster_name = self.cluster_var.get().strip()
            if not cluster_name:
                messagebox.showwarning("Uyarı", "Lütfen bir Large Cluster kategorisi seçin.")
                self.btn_start.config(state="normal")
                self.btn_pause.config(state="disabled")
                self.btn_stop.config(state="disabled")
                return
            threading.Thread(target=self._search_worker, args=(cluster_name,), daemon=True).start()

    def _effect_search_worker(self, cluster_name: str, selected_stats: list):
        """
        35% Effect modu worker.
        Sabit: %35 increased effect (1. prefix) + cluster base enchant
        Arama: seçili prefixlerden 1'i + seçili suffixlerden 2'si (1P+2S)
        """
        try:
            # Cluster option ID'yi bul
            opt_id = find_cluster_option_id(self.stats, cluster_name)
            if not opt_id:
                self._log(f"[Hata] Cluster option id bulunamadı: {cluster_name}")
                return

            # 35% effect stat ID'sini bul
            effect_id = find_effect_stat_id(self.stats)

            prefixes = [(sid, mv) for sid, mv, side in selected_stats if side == "prefix"]
            suffixes = [(sid, mv) for sid, mv, side in selected_stats if side == "suffix"]

            if not suffixes:
                self._log("[Hata] En az bir suffix seçili olmalı.")
                return

            # Kombinasyonlar: 1 prefix + 2 suffix (prefix yoksa sadece 2 suffix)
            if prefixes:
                combos = []
                for p in prefixes:
                    for s1, s2 in itertools.combinations(suffixes, 2):
                        combos.append([p, s1, s2])
            else:
                combos = [list(pair) for pair in itertools.combinations(suffixes, 2)]

            total_jobs = len(combos)
            n_workers = len(_REQUESTERS)
            self._log(f"[İş] {total_jobs} kombinasyon taranacak. ({n_workers} paralel worker)")

            combo_queue = queue.Queue()
            for combo in combos:
                combo_queue.put(combo)

            completed = [0]
            lock = threading.Lock()

            def worker_fn(req):
                while not self._stop_flag:
                    while self.paused and not self._stop_flag:
                        time.sleep(0.2)
                    try:
                        combo = combo_queue.get(timeout=1)
                    except queue.Empty:
                        break

                    # Grup 1: %35 effect (ayrı stats grubu)
                    group1_filters = [
                        {"id": effect_id, "value": {"min": 35}}
                    ]

                    combo_names = []
                    for stat_id, min_val in combo:
                        name = next((n for n,sid,d,s,_ in SMALL_PASSIVE_STATS if sid==stat_id), stat_id)
                        combo_names.append(name)

                    txt = " + ".join(combo_names)

                    stats_groups = [
                        # Grup 1: %35 effect
                        {"type": "and", "filters": group1_filters},
                        # Grup 2: 12 passive
                        {"type": "and", "filters": [
                            {"id": "enchant.stat_3086156145", "value": {"min": 12, "max": 12}}
                        ]},
                        # Grup 3: cluster base tipi
                        {"type": "and", "filters": [
                            build_cluster_base_filter(opt_id)
                        ]},
                    ]
                    # Grup 4+: seçili statlar her biri ayrı grup
                    for stat_id, min_val in combo:
                        stats_groups.append({"type": "and", "filters": [
                            {"id": stat_id, "value": {"min": min_val}}
                        ]})

                    body = {
                        "query": {
                            "status": {"option": "securable"},
                            "type": "Large Cluster Jewel",
                            "stats": stats_groups,
                            "filters": {
                                "type_filters": {"filters": {
                                    "category": {"option": "jewel.cluster"}
                                }},
                                "misc_filters": {"filters": {
                                    "ilvl": {"min": 84}
                                }},
                                "trade_filters": {"filters": {"sale_type": {"option": "priced"}}}
                            }
                        },
                        "sort": {"price": "asc"}
                    }

                    try:
                        search = req.send_request(f"{POE_TRADE_BASE}/search/{self.league_id}", data=body)
                        if not search:
                            combo_queue.task_done()
                            continue

                        total = int(search.get("total", 0))
                        qid = search.get("id", "")
                        ids = search.get("result", [])[:10]
                        link = f"https://www.pathofexile.com/trade/search/{self.league_id}/{qid}"

                        if total <= 0 or not ids:
                            self._append_result(txt, 0.0, 0.0, 0.0, "0", "?", "?", link)
                            self._log(f"[—] {txt} → ilan yok")
                            combo_queue.task_done()
                            continue

                        joined = ",".join(ids)
                        fetch_url = f"{POE_TRADE_BASE}/fetch/{quote(joined)}?query={quote(qid)}"
                        fetch = req.send_request(fetch_url, is_fetch=True)

                        results = fetch.get("result", []) if fetch else []
                        prices, ages = [], []
                        for r in results:
                            try:
                                li = r["listing"]["price"]
                                amount = float(li["amount"])
                                curr = li["currency"].lower()
                                chaos = amount * self.rates.get(curr, 1.0)
                                if chaos > 0:
                                    prices.append(chaos)
                                    ages.append(_format_age(r["listing"]["indexed"]))
                            except Exception:
                                continue

                        if not prices:
                            self._append_result(txt, 0.0, 0.0, 0.0, str(total), "?", "?", link)
                            combo_queue.task_done()
                            continue

                        cheapest = min(prices)
                        max_price = max(prices)
                        avg_price = sum(prices) / len(prices)

                        def _avg_age(age_list):
                            vals = []
                            for a in age_list:
                                if a.endswith("m"): vals.append(int(a[:-1])/60)
                                elif a.endswith("h"): vals.append(int(a[:-1]))
                                elif a.endswith("d"): vals.append(int(a[:-1])*24)
                            if not vals: return "?"
                            avg_h = sum(vals)/len(vals)
                            if avg_h < 1: return f"{int(avg_h*60)}m"
                            if avg_h < 24: return f"{int(avg_h)}h"
                            return f"{int(avg_h/24)}d"

                        age_cheapest = ages[prices.index(cheapest)] if ages else "?"
                        age_avg = _avg_age(ages)

                        # interval mesajı
                        if req.interval_message:
                            self._log(req.interval_message)
                            req.interval_message = None

                        self._append_result(
                            txt,
                            cheapest,
                            max_price,
                            avg_price,
                            str(total),
                            age_cheapest,
                            age_avg,
                            link,
                        )
                        self._log(
                            f"[OK] {txt} -> min={cheapest:.1f}c | max={max_price:.1f}c "
                            f"| ort={avg_price:.1f}c | ilan={total}"
                        )
                        if link:
                            self._log(f"🔗 {link}")

                    except Exception as e:
                        self._log(f"[Hata] {txt}: {e}")

                    with lock:
                        completed[0] += 1
                    combo_queue.task_done()

            threads = []
            for req in _REQUESTERS:
                t = threading.Thread(target=worker_fn, args=(req,), daemon=True)
                t.start()
                threads.append(t)
            for t in threads:
                t.join()

            if not self._stop_flag:
                self._log(f"[Bitti] Tarama tamamlandı. ({completed[0]} kombinasyon)")
            else:
                self._log("[DURDUR] Kullanıcı tarafından durduruldu.")
        except Exception as e:
            self._log(f"[Hata] {e}")
        finally:
            self.btn_start.config(state="normal")
            self.btn_pause.config(state="disabled")
            self.btn_stop.config(state="disabled")

    def _search_worker(self, cluster_name: str):
        try:
            cluster = find_cluster_by_name(self.clusters, cluster_name)
            if not cluster:
                self._log(f"[Hata] Cluster bulunamadı: {cluster_name}")
                return

            opt_id = find_cluster_option_id(self.stats, cluster["clusterName"])
            if not opt_id:
                self._log(f"[Hata] Cluster option id bulunamadı: {cluster_name}")
                return

            notables = cluster.get("notables", [])
            prefixes = [n["notableName"] for n in notables if n.get("side") == "prefix"]
            suffixes = [n["notableName"] for n in notables if n.get("side") == "suffix"]

            pref_pairs = list(itertools.combinations(prefixes, 2))
            total_jobs = len(pref_pairs) * max(1, len(suffixes))
            n_workers = len(_REQUESTERS)
            self._log(f"[İş] {total_jobs} kombinasyon taranacak. ({n_workers} paralel worker)")

            # Kombinasyonları queue'ya doldur
            combo_queue = queue.Queue()
            for pp in pref_pairs:
                for s in suffixes:
                    combo_names = [pp[0], pp[1], s]
                    ids = resolve_notable_ids_from_file(self.clusters, cluster_name, combo_names)
                    if ids:
                        combo_queue.put((combo_names, ids))
                    else:
                        self._log(f"[⚠️] Stat bulunamadı: {' + '.join(combo_names)}")

            active_threads = []
            completed = [0]
            lock = threading.Lock()

            def worker_fn(req):
                while not self._stop_flag:
                    while self.paused and not self._stop_flag:
                        time.sleep(0.2)
                    try:
                        combo_names, ids = combo_queue.get(timeout=1)
                    except queue.Empty:
                        break

                    txt = " + ".join(combo_names)
                    try:
                        cheapest, max_price, avg_price, listings, link, age_cheapest, age_avg10 = search_large_cluster_combination(
                            self.league_id, self.stats, opt_id, ids, self.rates,
                            max_fetch=10, requester=req
                        )
                    except Exception as e:
                        self._log(f"[Hata] {txt}: {e}")
                        combo_queue.task_done()
                        continue

                    listings = listings or 0
                    listings_str = "?" if listings == 0 else str(listings)

                    self._append_result(
                        txt,
                        cheapest or 0.0,
                        max_price or 0.0,
                        avg_price or 0.0,
                        listings_str,
                        age_cheapest or "?",
                        age_avg10 or "?",
                        link or ""
                    )
                    # İlk başarılı istekten sonra interval mesajını logla
                    if req.interval_message:
                        self._log(req.interval_message)
                        req.interval_message = None

                    self._log(
                        f"[OK] {txt} -> min={(cheapest or 0.0):.1f}c | "
                        f"max={(max_price or 0.0):.1f}c | "
                        f"ort={(avg_price or 0.0):.1f}c | ilan={listings_str}"
                    )
                    if link:
                        self._log(f"🔗 {link}")

                    with lock:
                        completed[0] += 1

                    combo_queue.task_done()

            # Her requester için ayrı thread aç
            for req in _REQUESTERS:
                t = threading.Thread(target=worker_fn, args=(req,), daemon=True)
                t.start()
                active_threads.append(t)

            for t in active_threads:
                t.join()

            if not self._stop_flag:
                self._log(f"[Bitti] Tarama tamamlandı. ({completed[0]} kombinasyon)")
            else:
                self._log("[DURDUR] Kullanıcı tarafından durduruldu.")
        except Exception as e:
            self._log(f"[Hata] {e}")
        finally:
            self.btn_start.config(state="normal")
            self.btn_pause.config(state="disabled")
            self.btn_stop.config(state="disabled")


if __name__ == "__main__":
    app = App()
    app.mainloop()
