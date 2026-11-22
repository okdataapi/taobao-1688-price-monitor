#!/usr/bin/env python3
"""Monitor product prices on Taobao, 1688, Xianyu and Douyin Shop over time.

Each run searches the keywords you name on the platforms you pick (one page each by default), reads the products
you track by ID, appends one row per product to <out>/snapshots.csv, and prints a short report: the lowest, median
and highest price on each platform, the tracked products, the biggest price drops since the last run, and the
products that are new. Run it every day from cron or GitHub Actions and the CSV becomes a price history.

Data comes from the okdata API (https://okdata.online/?src=gh-taobao-1688-price-monitor). A search page is $0.043
on Taobao, $0.022 on 1688 and Xianyu and $0.054 on Douyin Shop; the live prices are read from the free catalog
before every run. Python 3.9+, standard library only. The key goes in the OKDATA_API_KEY environment variable.

    python3 monitor.py --keyword 露营灯
    python3 monitor.py --keyword 保温杯 --platforms all --track 1688:594208233163 --lang zh
"""
from __future__ import annotations

import argparse
import csv
import http.client
import json
import os
import re
import sys
import time
import unicodedata
import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

VERSION = "0.1.0"
SOURCE = "gh-taobao-1688-price-monitor"
API = os.environ.get("OKDATA_BASE_URL", "https://api.okdata.online").rstrip("/")
# platform: (search endpoint, detail endpoint). Fallback prices (USD) if the free catalog cannot be read.
PLATFORMS = {
    "taobao": ("taobao.products.search", "taobao.products.get"),
    "alibaba_1688": ("alibaba_1688.products.search", "alibaba_1688.products.get"),
    "xianyu": ("xianyu.products.search", "xianyu.products.get"),
    "douyin_shop": ("douyin_shop.products.search", "douyin_shop.products.get"),
}
PRICES = {
    "taobao.products.search": Decimal("0.043"), "taobao.products.get": Decimal("0.033"),
    "alibaba_1688.products.search": Decimal("0.022"), "alibaba_1688.products.get": Decimal("0.022"),
    "xianyu.products.search": Decimal("0.022"), "xianyu.products.get": Decimal("0.022"),
    "douyin_shop.products.search": Decimal("0.054"), "douyin_shop.products.get": Decimal("0.039"),
}
DEFAULT_PLATFORMS = ("taobao", "alibaba_1688")
ALIASES = {"1688": "alibaba_1688", "tmall": "taobao", "goofish": "xianyu", "douyin": "douyin_shop"}
SORTED_BY_SALES = ("taobao", "alibaba_1688")  # Xianyu has no sales order and Douyin Shop search no sort at all
FIELDS = ["run_at", "source", "platform", "product_id", "title", "price", "price_high", "sku_low", "original_price",
          "price_tiers", "sold", "shop", "location", "min_order", "wants", "commission_rate", "url"]
CSV_NAME = "snapshots.csv"
TITLE_LIMIT = 100  # characters kept in the CSV
REPORT_TITLE_LIMIT = 36  # characters shown in the report
KEYWORD_LIMIT = 50
TRACK = "track"
# Errors that every later call would hit too, so the run stops instead of trying the next call.
STOP_CODES = {"unauthorized", "insufficient_balance", "key_budget_exceeded", "cost_cap_exceeded", "key_scope_denied",
              "account_suspended", "budget_reached"}
RETRY_STATUSES = {429, 500, 502, 503, 504}
WHITESPACE = re.compile("[\t\n\v\f\r    　]+")
PRODUCT_ID = re.compile(r"^[0-9]{5,25}$")
PRODUCT_URLS = [  # a product link copied from the browser, and the platform it belongs to
    ("taobao", re.compile(r"(?:^|[/.])(?:taobao\.com|tmall\.com|tmall\.hk)/[^#]*[?&]id=([0-9]{5,25})")),
    ("alibaba_1688", re.compile(r"(?:^|[/.])1688\.com/offer/([0-9]{5,25})\.html")),
    ("xianyu", re.compile(r"(?:^|[/.])goofish\.com/[^#]*[?&](?:id|itemId)=([0-9]{5,25})")),
    ("douyin_shop", re.compile(r"(?:^|[/.])jinritemai\.com/[^#]*[?&]id=([0-9]{5,25})")),
]
INTEGER = re.compile(r"-?[0-9]+")
AMOUNT = re.compile(r"[0-9]+(\.[0-9]+)?")
AMOUNT_LIMIT = Decimal("1e12")  # no price or count from a shop is this large
LOCATIONS = ("ships_from", "location", "area", "seller_city")  # where each platform says the product or seller is

Call = Tuple[str, str, str, Dict[str, str]]  # (source in the CSV, platform, endpoint, parameters)

NAMES = {
    "en": {"taobao": "Taobao", "alibaba_1688": "1688", "xianyu": "Xianyu", "douyin_shop": "Douyin Shop"},
    "zh": {"taobao": "淘宝", "alibaba_1688": "1688", "xianyu": "闲鱼", "douyin_shop": "抖音电商"},
}
TEXT = {
    "en": {
        "run": "China e-commerce price monitor {current} ",
        "previous": "(previous run {previous})",
        "first": "(first run)",
        "prices": "Prices for {keyword}, in yuan:",
        "columns": ("platform", "items", "lowest", "median", "highest"),
        "ratio": "Taobao median is {ratio}x the 1688 median.",
        "tracked": "Tracked products:",
        "was": "was ¥{price}",
        "no_price": "no price in this answer",
        "sold": "{n} sold",
        "sep": ", ",
        "first_saved": "First snapshot saved. Run it again tomorrow, or a few hours later, to see price drops and new "
                       "products.",
        "drops": "Biggest price drops since the last run:",
        "no_drops": "No price went down.",
        "no_pairs": "No product has a price in this run and an earlier one yet.",
        "moves": "Of {n} products seen before: {down} cheaper, {up} dearer, {same} unchanged.",
        "new": "New in the search results, never seen before: {n}",
        "more": "...and {n} more in the CSV",
    },
    "zh": {
        "run": "电商价格监控 {current}",
        "previous": "（上次 {previous}）",
        "first": "（首次运行）",
        "prices": "「{keyword}」的价格（元）：",
        "columns": ("平台", "件数", "最低", "中位", "最高"),
        "ratio": "淘宝的中位价是 1688 的 {ratio} 倍。",
        "tracked": "跟踪的商品：",
        "was": "之前 ¥{price}",
        "no_price": "这次没有价格",
        "sold": "销量 {n}",
        "sep": "，",
        "first_saved": "已存下第一份快照。明天（或者几小时后）再跑一次，就能看到降价和新出现的商品。",
        "drops": "和上次比降价最多：",
        "no_drops": "没有商品降价。",
        "no_pairs": "还没有能和之前比价的商品。",
        "moves": "之前见过的 {n} 个商品：降价 {down} 个，涨价 {up} 个，没变 {same} 个。",
        "new": "搜索结果里新出现的商品：{n} 个",
        "more": "……另外 {n} 个在 CSV 里",
    },
}


def links(lang: str) -> Tuple[str, str]:
    prefix = "/zh" if lang == "zh" else ""
    return (f"https://okdata.online{prefix}/signup/?src={SOURCE}", f"https://okdata.online{prefix}/console/?src={SOURCE}")


class ApiError(Exception):
    def __init__(self, code: str, message: str, *, charged: Optional[bool] = False, retry: str = "no",
                 retry_after: Optional[float] = None, amount: Any = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code, self.charged, self.retry, self.retry_after = code, charged, retry, retry_after
        self.amount = amount


class OutputError(Exception):
    """The CSV cannot be used: other columns, or not a writable file."""


class Okdata:
    """The okdata calls this script needs, with safe retries and a hard spending cap."""

    def __init__(self, key: Optional[str], budget: Optional[Decimal] = None,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.key = key
        self.budget = budget
        self.sleep = sleep
        self.spent = Decimal("0")
        self.caps = dict(PRICES)

    def _headers(self, idempotency_key: Optional[str]) -> Dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": f"{SOURCE}/{VERSION} (python)"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def prices(self) -> Dict[str, Decimal]:
        """Current prices from the free catalog (no key needed); the built-in table if it cannot be read."""
        try:
            data = request_json(f"{API}/v1/catalog", self._headers(None), self.sleep)["data"]
            live = {e["id"]: dollars(e.get("maxCharge")) for e in data["endpoints"]}
            self.caps = {k: live.get(k) or v for k, v in PRICES.items()}
        except (ApiError, KeyError, TypeError, AttributeError):
            self.caps = dict(PRICES)
        return self.caps

    def call(self, endpoint: str, **params: Any) -> Dict[str, Any]:
        cap = self.caps.get(endpoint, Decimal("0"))
        if self.budget is not None and self.spent + cap > self.budget:
            raise ApiError("budget_reached", f"the next call could cost ${usd(cap)} and pass the --budget of "
                                             f"${usd(self.budget)}")
        query = urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{API}/v1/{endpoint.replace('.', '/')}?{query}"
        try:
            body = request_json(url, self._headers(str(uuid.uuid4())), self.sleep)
        except ApiError as err:
            if err.charged is True:  # keep the spend in step with the amount the API reports
                self.spent += dollars(err.amount) or Decimal("0")
            raise
        self.spent += dollars(((body.get("meta") or {}).get("billing") or {}).get("amount")) or Decimal("0")
        return body


def _http_error(exc: HTTPError) -> ApiError:
    try:
        body = json.loads(exc.read().decode("utf-8"))
    except (ValueError, OSError, http.client.HTTPException):  # not JSON, or the body was cut off
        body = None
    finally:
        exc.close()
    if isinstance(body, dict) and "code" in body:
        return ApiError(str(body["code"]), str(body.get("message")), charged=body.get("charged", False),
                        retry=str(body.get("retry", "no")), retry_after=body.get("retry_after_seconds"),
                        amount=body.get("amount"))
    return ApiError(f"http_{exc.code}", str(exc.reason), charged=None,
                    retry="yes" if exc.code in RETRY_STATUSES else "no")


def request_json(url: str, headers: Dict[str, str], sleep: Callable[[float], None] = time.sleep) -> Dict[str, Any]:
    """GET with up to 2 retries that reuse the same Idempotency-Key, so a lost answer is replayed instead of run
    twice. After a lost answer the call may still be running on the server, so a rate_limited reply is waited out."""
    retries, waits, ambiguous = 0, 0, False
    while True:
        try:
            with urlopen(Request(url, headers=headers), timeout=90) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            if isinstance(body, dict) and body.get("code") == "ok":
                return body
            err = (ApiError(str(body.get("code")), str(body.get("message"))) if isinstance(body, dict)
                   else ApiError("bad_response", "unexpected answer", charged=None, retry="same_key"))
        except HTTPError as exc:
            err = _http_error(exc)
        except (OSError, ValueError, http.client.HTTPException) as exc:  # network, timeout, cut-off or non-JSON
            err = ApiError("connection_error", str(exc), charged=None, retry="same_key")
        ambiguous = ambiguous or err.charged is None
        if ambiguous and err.code == "rate_limited" and waits < 5:
            waits += 1
            sleep(_wait(err.retry_after, 1.0))
            continue
        if err.retry not in ("yes", "same_key") or retries == 2:
            if ambiguous and err.charged is False:
                err.charged = None  # an earlier attempt may still finish
            raise err
        sleep(_wait(err.retry_after, 2.0 ** retries))
        retries += 1


def _wait(value: Any, default: float) -> float:
    """Seconds to sleep: the server's hint if it is a sane number, capped at 30."""
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return default
    return min(max(seconds, 0.0), 30.0)


def use_utf8() -> None:
    """Chinese titles in and out, also on Windows consoles and pipes."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace" if stream is sys.stderr else "strict")


def dollars(value: Any) -> Optional[Decimal]:
    """An amount from the API ("0.022", 0.022 or 1e-8) as a Decimal; None if it is not a sane amount."""
    if isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return amount if amount.is_finite() and amount >= 0 else None


def usd(amount: Decimal) -> str:
    """0.020 -> "0.02", 1.50 -> "1.5", 100 -> "100"."""
    return format(amount.normalize(), "f")


def yuan(amount: Decimal) -> str:
    """A price as the report shows it: 8.1 -> "8.10", 1299 -> "1,299.00"."""
    return f"{amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,}"


def charged(err: ApiError) -> str:
    return {True: "yes", False: "no"}.get(err.charged, "unknown")  # type: ignore[arg-type]


def cell(value: Any) -> Any:
    """Text that starts like a spreadsheet formula gets a leading ' so Excel shows it instead of running it."""
    return "'" + value if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def clip(text: Any, limit: int) -> str:
    """One line, at most `limit` characters, with … where it was cut."""
    line = str(text or "").encode("utf-16", "surrogatepass").decode("utf-16", "replace")
    line = WHITESPACE.sub(" ", line).strip(" ")
    return line if len(line) <= limit else line[: limit - 1].rstrip(" ") + "…"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- what to monitor ---------------------------------------------------------------------------------------------

def keyword(value: str) -> str:
    text = WHITESPACE.sub(" ", value).strip(" ")
    if not text or len(text) > KEYWORD_LIMIT:
        raise argparse.ArgumentTypeError(f"not a search keyword (1 to {KEYWORD_LIMIT} characters): {value!r}")
    return text


def platform_name(value: str) -> str:
    name = value.strip().lower()
    name = ALIASES.get(name, name)
    if name not in PLATFORMS:
        raise argparse.ArgumentTypeError(f"not a platform: {value!r} (taobao, 1688, xianyu or douyin_shop)")
    return name


def platform_list(value: str) -> List[str]:
    """"all", or a comma-separated list such as "taobao,1688"."""
    if value.strip().lower() == "all":
        return list(PLATFORMS)
    names = [platform_name(v) for v in value.split(",") if v.strip()]
    if not names:
        raise argparse.ArgumentTypeError("name at least one platform, or all")
    return list(dict.fromkeys(names))


def track(value: str) -> Tuple[str, str]:
    """PLATFORM:ID (1688:594208233163) or a product link copied from the browser."""
    text = value.strip()
    for platform, pattern in PRODUCT_URLS:
        found = pattern.search(text)
        if found:
            return platform, found.group(1)
    name, sep, product_id = text.partition(":")
    if sep and PRODUCT_ID.match(product_id.strip()):
        try:
            return platform_name(name), product_id.strip()
        except argparse.ArgumentTypeError:
            pass
    raise argparse.ArgumentTypeError(
        f"not a product to track: {value!r} (use PLATFORM:ID such as 1688:594208233163, or the product link)")


def plan_calls(keywords: List[str], platforms: List[str], tracked: List[Tuple[str, str]], sort: str) -> List[Call]:
    calls: List[Call] = []
    for k in dict.fromkeys(keywords):
        for p in platforms:
            params = {"query": k}
            if p in SORTED_BY_SALES:
                params["sort"] = sort
            calls.append((f"keyword:{k}", p, PLATFORMS[p][0], params))
    for p, product_id in dict.fromkeys(tracked):
        calls.append((TRACK, p, PLATFORMS[p][1], {"id": product_id}))
    return calls


def plan_cost(caps: Dict[str, Decimal], calls: List[Call], pages: int) -> Decimal:
    return sum((caps[endpoint] * (1 if source == TRACK else pages) for source, _, endpoint, _ in calls), Decimal("0"))


# --- fetching and storing ----------------------------------------------------------------------------------------

def products(ok: Okdata, call: Call, pages: int, cached: List[str]) -> Iterator[Dict[str, Any]]:
    """The products of one search (page by page) or one tracked product. When an answer is a copy the API fetched
    a little earlier (meta.cached), its fetch time goes into `cached`."""
    source, _, endpoint, params = call
    cursor = None
    for _ in range(1 if source == TRACK else pages):
        body = ok.call(endpoint, **params, cursor=cursor, view="full")
        meta, data, page = (part(body, k) for k in ("meta", "data", "page"))
        if meta.get("cached"):
            cached.append(str(meta.get("fetched_at") or "?"))
        if source == TRACK:
            if isinstance(data.get("item"), dict):
                yield {**data["item"], "id": data["item"].get("id") or params["id"]}
            return
        items = data.get("items") if isinstance(data.get("items"), list) else []
        yield from (i for i in items if isinstance(i, dict) and i.get("id"))  # no ID, nothing to follow
        cursor = page.get("next_cursor")
        if not cursor:
            return


def part(body: Dict[str, Any], name: str) -> Dict[str, Any]:
    """body[name] if it is an object, else an empty one, so an odd answer cannot crash the run."""
    value = body.get(name)
    return value if isinstance(value, dict) else {}


def amount(value: Any) -> Optional[Decimal]:
    """A price or count from the API as a Decimal, or None; never a bool, never negative, never absurdly large."""
    if isinstance(value, str) and not AMOUNT.fullmatch(value.strip()):
        return None
    found = dollars(value)
    return found if found is None or found < AMOUNT_LIMIT else None


def plain(value: Optional[Decimal]) -> Optional[str]:
    return None if value is None else usd(value)


def whole(value: Any) -> Optional[int]:
    found = amount(value)
    return None if found is None else int(found)


def to_row(run_at: str, source: str, platform: str, item: Dict[str, Any]) -> Dict[str, Any]:
    ext = item.get("ext") if isinstance(item.get("ext"), dict) else {}
    shop = item.get("shop") if isinstance(item.get("shop"), dict) else {}
    variants = ext.get("skus") if isinstance(ext.get("skus"), list) else []
    skus = [amount(s.get("price")) for s in variants if isinstance(s, dict)]
    skus = [p for p in skus if p is not None]
    high = amount(ext.get("price_max")) or (max(skus) if skus else None)
    tiers = ext.get("tiered_prices")
    detail = source == TRACK
    return {
        "run_at": run_at,
        "source": source,
        "platform": platform,
        "product_id": str(item.get("id") or ""),
        "title": clip(item.get("title"), TITLE_LIMIT),
        "price": plain(amount(item.get("price"))),
        "price_high": plain(high),
        "sku_low": plain(min(skus)) if skus else None,
        "original_price": plain(amount(item.get("original_price"))),
        "price_tiers": json.dumps(tiers, ensure_ascii=False, separators=(",", ":")) if tiers else None,
        "sold": whole(item.get("sold")),
        "shop": clip(shop.get("name"), TITLE_LIMIT),
        "location": clip(next((ext[k] for k in LOCATIONS if ext.get(k)), ""), 40),
        "min_order": whole(ext.get("min_order")),
        "wants": whole(ext.get("wants")) if detail else None,  # only the detail answer counts wants
        "commission_rate": plain(amount(ext.get("commission_rate"))),
        "url": item.get("url") or "",
    }


def read_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:  # -sig: also reads a file a spreadsheet saved
        reader = csv.DictReader(f, restval="")
        if reader.fieldnames != FIELDS:
            raise OutputError(f"{path} has other columns than this monitor writes; use another --out")
        return list(reader)


def check_writable(path: Path) -> None:
    """Fail before any paid call if the CSV could not be written afterwards."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not path.is_file():
        raise OutputError(f"{path} is not a file")
    if not os.access(path if path.exists() else path.parent, os.W_OK):
        raise OutputError(f"{path} is not writable")


def ends_with_newline(path: Path) -> bool:
    with path.open("rb") as f:
        f.seek(-1, os.SEEK_END)
        return f.read(1) in (b"\n", b"\r")


def append_rows(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fresh = not path.exists() or path.stat().st_size == 0
    newline_first = not fresh and not ends_with_newline(path)  # a file saved without a final newline
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        if newline_first:
            f.write("\n")
        if fresh:
            writer.writeheader()
        writer.writerows({k: cell("" if v is None else v) for k, v in row.items()} for row in rows)


# --- the report --------------------------------------------------------------------------------------------------

Key = Tuple[str, str, str]  # (source, platform, product_id)


def key(row: Dict[str, str]) -> Key:
    return row["source"], row["platform"], row["product_id"]


def price_of(row: Dict[str, str]) -> Optional[Decimal]:
    """The row's price, or None when there is none (or it is 0, which no comparison should use)."""
    found = amount(row["price"]) if row["price"] else None
    return found if found else None


def number(value: Any) -> Optional[int]:
    return int(value) if value is not None and INTEGER.fullmatch(str(value)) else None


def median(values: List[Decimal]) -> Decimal:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def width(text: str) -> int:
    """Columns the text takes in a terminal: Chinese characters take two."""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def pad(text: str, columns: int) -> str:
    return text + " " * max(columns - width(text), 0)


def table_row(cells: Tuple[str, ...]) -> str:
    """The platform left-aligned in 12 columns, then the numbers right-aligned in 6, 10, 10 and 10."""
    first, *rest = cells
    return "  " + pad(first, 12) + "".join(" " * max(n - width(c), 0) + c for c, n in zip(rest, (6, 10, 10, 10)))


def by_key(rows: List[Dict[str, str]]) -> Dict[Key, Dict[str, str]]:
    """One row per product, the first one, so a product on two pages of one search counts once."""
    found: Dict[Key, Dict[str, str]] = {}
    for row in rows:
        found.setdefault(key(row), row)
    return found


def last_seen(rows: List[Dict[str, str]], current: str) -> Dict[Key, Dict[str, str]]:
    """Each product's row from the latest earlier run that has it, so a run that missed a platform (a failed call,
    a one-off run with other keywords) does not stop the comparison."""
    runs: Dict[str, List[Dict[str, str]]] = {}
    for r in rows:
        if r["run_at"] < current:
            runs.setdefault(r["run_at"], []).append(r)
    found: Dict[Key, Dict[str, str]] = {}
    for run_at in sorted(runs):
        found.update(by_key(runs[run_at]))
    return found


def price_tables(now: List[Dict[str, str]], lang: str) -> List[str]:
    """Per keyword: items, lowest, median and highest price on each platform."""
    t, names = TEXT[lang], NAMES[lang]
    lines: List[str] = []
    for source in dict.fromkeys(r["source"] for r in now if r["source"] != TRACK):
        mine = list(by_key([r for r in now if r["source"] == source]).values())
        lines += ["", t["prices"].format(keyword=source[len("keyword:"):])]
        lines.append(table_row(t["columns"]))
        medians: Dict[str, Decimal] = {}
        for platform in PLATFORMS:
            rows = [r for r in mine if r["platform"] == platform]
            prices = [p for p in (price_of(r) for r in rows) if p is not None]
            if not rows:
                continue
            stats = ["", "", ""]
            if prices:
                medians[platform] = median(prices)
                stats = [yuan(min(prices)), yuan(medians[platform]), yuan(max(prices))]
            lines.append(table_row((names[platform], str(len(rows)), *stats)))
        if medians.get("taobao") and medians.get("alibaba_1688"):
            ratio = (medians["taobao"] / medians["alibaba_1688"]).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
            lines.append("  " + t["ratio"].format(ratio=ratio))
    return lines


def product_line(lead: str, row: Dict[str, str], lang: str, extra: str = "") -> str:
    parts = [lead, NAMES[lang][row["platform"]], row["shop"] or "?", extra, clip(row["title"], REPORT_TITLE_LIMIT)]
    return "  " + " · ".join(p for p in parts if p)


def tracked_lines(rows: List[Dict[str, str]], now: List[Dict[str, str]], current: str, lang: str) -> List[str]:
    t = TEXT[lang]
    mine = [r for r in now if r["source"] == TRACK]
    if not mine:
        return []
    before = last_seen(rows, current)
    lines = ["", t["tracked"]]
    for r in by_key(mine).values():
        price, old = price_of(r), before.get(key(r))
        lead = f"¥{yuan(price)}" if price is not None else t["no_price"]
        extra = []
        if old is not None and price_of(old) is not None:
            extra.append(t["was"].format(price=yuan(price_of(old))))  # type: ignore[arg-type]
        if number(r["sold"]) is not None:
            extra.append(t["sold"].format(n=f"{number(r['sold']):,}"))
        lines.append(product_line(lead, r, lang, t["sep"].join(extra)))
        lines.append(f"    {r['url']}")
    return lines


Pair = Tuple[Decimal, Decimal, Dict[str, str]]  # (price now, price when last seen, row)


def price_pairs(rows: List[Dict[str, str]], now: List[Dict[str, str]], current: str) -> List[Pair]:
    """Every product priced now and when it was last seen, compared within the same search or the same tracked
    read, once per product: when a tracked product also turns up in a search, its detail price is the one that
    counts."""
    before = last_seen(rows, current)
    found: Dict[Tuple[str, str], Pair] = {}
    for k, r in sorted(by_key(now).items(), key=lambda kv: kv[0][0] != TRACK):  # tracked reads first
        new, old = price_of(r), price_of(before[k]) if k in before else None
        if new is not None and old is not None:
            found.setdefault((r["platform"], r["product_id"]), (new, old, r))
    return list(found.values())


def drop_lines(rows: List[Dict[str, str]], now: List[Dict[str, str]], current: str, top: int, lang: str) -> List[str]:
    """How many prices fell or rose since each product was last seen, and the biggest relative drops."""
    t = TEXT[lang]
    pairs = price_pairs(rows, now, current)
    down = sorted((p for p in pairs if p[0] < p[1]), key=lambda p: ((p[0] - p[1]) / p[1], p[0] - p[1], key(p[2])))
    up = sum(1 for p in pairs if p[0] > p[1])
    lines = ["", t["drops"]]
    if not pairs:
        return lines + ["  " + t["no_pairs"]]
    lines.append("  " + t["moves"].format(n=len(pairs), down=len(down), up=up, same=len(pairs) - len(down) - up))
    if not down:
        lines.append("  " + t["no_drops"])
    for new, old, r in down[:top]:
        share = ((old - new) * 100 / old).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        lead = f"-¥{yuan(old - new)} (-{share}%)"
        lines.append(product_line(lead, r, lang, f"¥{yuan(old)} → ¥{yuan(new)}"))
        lines.append(f"    {r['url']}")
    return lines


def new_lines(rows: List[Dict[str, str]], now: List[Dict[str, str]], current: str, top: int, lang: str) -> List[str]:
    """Search results never seen for the same keyword and platform before, best sellers of each platform first."""
    t = TEXT[lang]
    seen = {key(r) for r in rows if r["run_at"] < current}
    fresh = [r for k, r in by_key(now).items() if r["source"] != TRACK and k not in seen]
    order = list(PLATFORMS)
    rank: Dict[str, int] = {}
    ranked = []
    for r in sorted(fresh, key=lambda r: (order.index(r["platform"]), -(number(r["sold"]) or 0), r["product_id"])):
        rank[r["platform"]] = rank.get(r["platform"], 0) + 1
        ranked.append((rank[r["platform"]], order.index(r["platform"]), r))
    ranked.sort(key=lambda x: (x[0], x[1]))  # round robin: each platform's best seller, then the second ones...
    lines = ["", t["new"].format(n=len(fresh))]
    for _, _, r in ranked[:top]:
        price = price_of(r)
        lines.append(product_line(f"¥{yuan(price)}" if price is not None else "?", r, lang))
        lines.append(f"    {r['url']}")
    if len(fresh) > top:
        lines.append("  " + t["more"].format(n=len(fresh) - top))
    return lines


def report(rows: List[Dict[str, str]], top: int, lang: str = "en") -> str:
    """Price spread per keyword and platform, the tracked products, then (from the second run on) the biggest price
    drops and the new products since the run before."""
    t = TEXT[lang]
    runs = sorted({r["run_at"] for r in rows})
    if not runs:
        return ""
    current = runs[-1]
    previous = runs[-2] if len(runs) > 1 else None
    now = [r for r in rows if r["run_at"] == current]
    lines = [t["run"].format(current=current) + (t["previous"].format(previous=previous) if previous else t["first"])]
    lines += price_tables(now, lang)
    lines += tracked_lines(rows, now, current, lang)
    if previous is None:
        lines += ["", t["first_saved"]]
    else:
        lines += drop_lines(rows, now, current, top, lang)
        lines += new_lines(rows, now, current, top, lang)
    return "\n".join(lines) + "\n"


# --- the command -------------------------------------------------------------------------------------------------

def hint(code: str, lang: str) -> str:
    sign_up, console = links(lang)
    return {
        "unauthorized": f"Check OKDATA_API_KEY, or get a key at {sign_up}",
        "insufficient_balance": f"Top up at {console} and run again.",
        "key_budget_exceeded": f"This key reached the spending limit set for it at {console}",
        "budget_reached": "Stopped at --budget.",
        "cost_cap_exceeded": "The account reached its daily spending allowance; it resets at the next UTC day.",
        "not_found": "Check the product ID and its platform.",
    }.get(code, "")


def describe(call: Call) -> str:
    source, platform, _, params = call
    return f"{source} {platform}" if source != TRACK else f"track {platform}:{params['id']}"


def print_plan(args: argparse.Namespace, ok: Okdata, calls: List[Call], most: Decimal, path: Path) -> None:
    pages = sum(1 if c[0] == TRACK else args.pages for c in calls)
    print(f"plan: {len(calls)} search(es) and tracked product(s) = up to {pages} call(s); at most ${usd(most)}",
          file=sys.stderr)
    for call in calls:
        each = "per page" if call[0] != TRACK else "per call"
        print(f"  {describe(call)}  ({call[2]}, ${usd(ok.caps[call[2]])} {each})", file=sys.stderr)
    print(f"  appends to {path}", file=sys.stderr)


def fetch_all(args: argparse.Namespace, ok: Okdata, calls: List[Call], path: Path, run_at: str) -> Tuple[int, int, bool]:
    """Every call in turn; rows are saved after each, so a later failure or Ctrl-C keeps what was paid for."""
    saved, failed, stopped = 0, 0, False
    for call in calls:
        rows: List[Dict[str, Any]] = []
        cached: List[str] = []
        try:
            for item in products(ok, call, args.pages, cached):
                rows.append(to_row(run_at, call[0], call[1], item))
            note = f" (prices as of {min(cached)})" if cached else ""
            print(f"{describe(call)}: {len(rows)} product{'' if len(rows) == 1 else 's'}{note}", file=sys.stderr)
        except ApiError as err:
            failed += 1
            print(f"{describe(call)}: {err} (charged: {charged(err)}). {hint(err.code, args.lang)}".rstrip(),
                  file=sys.stderr)
            if err.code in STOP_CODES:
                stopped = True
                break
        finally:
            if rows:
                append_rows(path, rows)
                saved += len(rows)
    return saved, failed, stopped


def run(args: argparse.Namespace, ok: Okdata, now: Callable[[], str]) -> int:
    path = Path(args.out) / CSV_NAME
    if args.report_only:
        sys.stdout.write(report(read_rows(path), args.top, args.lang))
        return 0
    calls = plan_calls(args.keyword or [], args.platforms, args.track or [], args.sort)
    most = plan_cost(ok.prices(), calls, args.pages)
    print_plan(args, ok, calls, most, path)
    if args.dry_run:
        return 0
    if most > args.budget:
        print(f"over the --budget of ${usd(args.budget)}; raise it or use fewer --pages", file=sys.stderr)
        return 3
    if not ok.key:
        print(f"OKDATA_API_KEY is not set. Get a key at {links(args.lang)[0]}", file=sys.stderr)
        return 2

    read_rows(path)  # refuse a foreign or unwritable CSV before spending anything
    check_writable(path)
    saved, failed, stopped = fetch_all(args, ok, calls, path, now())
    if saved:
        print(f"appended {saved} rows to {path}", file=sys.stderr)
        sys.stdout.write(report(read_rows(path), args.top, args.lang))
    print(f"spent ${usd(ok.spent)}", file=sys.stderr)
    if stopped or failed == len(calls):
        return 1
    return 4 if failed else 0


def money(value: str) -> Decimal:
    if not AMOUNT.fullmatch(value.strip()):
        raise argparse.ArgumentTypeError(f"not an amount in USD: {value!r}")
    return Decimal(value.strip())


def positive(value: str) -> int:
    if not re.fullmatch(r"[0-9]+", value.strip()) or int(value) < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return int(value)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        allow_abbrev=False,
        description="Monitor product prices on Taobao, 1688, Xianyu and Douyin Shop: append each product's price "
                    "and sales to a CSV, then report the price spread, price drops and new products (okdata API).")
    p.add_argument("--keyword", action="append", type=keyword, metavar="TEXT",
                   help="search keywords, as typed into the platform's search box (repeat for more)")
    p.add_argument("--platforms", type=platform_list, default=list(DEFAULT_PLATFORMS), metavar="LIST",
                   help="where to search: comma-separated taobao, 1688, xianyu, douyin_shop, or all "
                        "(default taobao,1688)")
    p.add_argument("--track", action="append", type=track, metavar="PLATFORM:ID",
                   help="a product to read by ID every run, as PLATFORM:ID (1688:594208233163) or its link "
                        "(repeat for more)")
    p.add_argument("--sort", choices=("sales", "default"), default="sales",
                   help="order of Taobao and 1688 results: sales or the platform's default (default sales)")
    p.add_argument("--pages", type=positive, default=1, metavar="N",
                   help="search pages per keyword and platform (default 1)")
    p.add_argument("--out", default="data", metavar="DIR", help="folder for snapshots.csv (default data)")
    p.add_argument("--top", type=positive, default=5, metavar="N",
                   help="how many price drops and new products to list (default 5)")
    p.add_argument("--budget", type=money, default=Decimal("0.5"), metavar="USD",
                   help="refuse runs that could cost more (USD, default 0.5)")
    p.add_argument("--lang", choices=tuple(TEXT), default="en", help="language of the report: en or zh (default en)")
    p.add_argument("--dry-run", action="store_true", help="print the plan and the most it can cost, then stop")
    p.add_argument("--report-only", action="store_true",
                   help="print the report for the CSV in --out again, without calling anything")
    args = p.parse_args(argv)
    if not (args.keyword or args.track or args.report_only):
        p.error("give at least one --keyword or --track")
    return args


def main(argv: Optional[List[str]] = None, now: Callable[[], str] = utc_now) -> int:
    use_utf8()
    args = parse_args(argv)
    ok = Okdata(os.environ.get("OKDATA_API_KEY", "").strip() or None, budget=args.budget)
    try:
        return run(args, ok, now)
    except (OutputError, OSError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
