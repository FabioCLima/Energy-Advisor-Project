"""
ANEEL data access for monthly tariff flags with explicit provenance.

Resolution order:
  1. In-memory cache for the current process
  2. On-disk cache for the current month
  3. ANEEL open data endpoint (when enabled)
  4. Local fallback values bundled with the project

The client is intentionally conservative: external fetch failures never break the
application and the caller can inspect provenance metadata to know whether the
result came from cache, API, or fallback.
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import certifi
from loguru import logger

_FALLBACK: dict[str, tuple[str, float]] = {
    "2026-02": ("vermelha_1", 0.03971),
    "2026-03": ("amarela", 0.01885),
    "2026-04": ("verde", 0.00000),
    "2026-05": ("verde", 0.00000),
}
_DEFAULT = ("verde", 0.00000)
_DEFAULT_CACHE = "data/aneel_bandeiras_cache.json"

_CKAN_URL = (
    "https://dadosabertos.aneel.gov.br/api/3/action/datastore_search"
    "?resource_id=0591b8f6-fe54-437b-b72b-1aa2efd46e42"
    "&limit=48"
    "&sort=DatInicioVigencia+desc"
)

_NAME_MAP: dict[str, str] = {
    "verde": "verde",
    "amarela": "amarela",
    "vermelha patamar 1": "vermelha_1",
    "vermelha patamar 2": "vermelha_2",
    "vermelha 1": "vermelha_1",
    "vermelha 2": "vermelha_2",
}


@dataclass(frozen=True)
class AneelFlagResolution:
    date_key: str
    bandeira: str
    adicional_brl: float
    data_source: str
    fetched_at: str | None
    fallback_used: bool
    cache_path: str


@dataclass(frozen=True)
class AneelCacheBundle:
    bandeiras: dict[str, tuple[str, float]]
    data_source: str
    fetched_at: str | None
    fallback_used: bool


def _slug(raw: str) -> str:
    lower = raw.strip().lower()
    for fragment, slug in _NAME_MAP.items():
        if fragment in lower:
            return slug
    return "verde"


def _parse_date(raw: Any) -> datetime | None:
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(raw).strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None


def _adicional(raw: Any) -> float:
    try:
        value = float(str(raw).replace(",", "."))
        return round(value / 1000.0 if value > 1.0 else value, 5)
    except (ValueError, TypeError):
        return 0.0


def _parse_records(records: list[dict[str, Any]]) -> dict[str, tuple[str, float]]:
    result: dict[str, tuple[str, float]] = {}
    for rec in records:
        start_raw = (
            rec.get("DatInicioVigencia")
            or rec.get("DatInicio")
            or rec.get("dat_inicio_vigencia")
            or ""
        )
        bandeira_raw = (
            rec.get("DscBandeira")
            or rec.get("NomBandeira")
            or rec.get("dsc_bandeira")
            or ""
        )
        adicional_raw = (
            rec.get("VlrEncargo")
            or rec.get("VlrAdicional")
            or rec.get("vlr_encargo")
            or 0.0
        )

        dt = _parse_date(start_raw)
        if dt is None:
            continue

        result[dt.strftime("%Y-%m")] = (_slug(str(bandeira_raw)), _adicional(adicional_raw))
    return result


def _make_ssl_context(allow_insecure_ssl: bool) -> ssl.SSLContext:
    if allow_insecure_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return ssl.create_default_context(cafile=certifi.where())


def _fetch_aneel(timeout: int = 10, allow_insecure_ssl: bool = False) -> AneelCacheBundle | None:
    req = urllib.request.Request(
        _CKAN_URL,
        headers={"User-Agent": "EcoHome-EnergyAdvisor/1.0"},
    )
    try:
        with urllib.request.urlopen(
            req,
            timeout=timeout,
            context=_make_ssl_context(allow_insecure_ssl),
        ) as resp:
            if getattr(resp, "status", 200) != 200:
                logger.warning("ANEEL API returned HTTP {}", getattr(resp, "status", "?"))
                return None
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        logger.warning("ANEEL API HTTP error: {}", exc.code)
        return None
    except urllib.error.URLError as exc:
        logger.warning("ANEEL API URL error: {}", exc)
        return None
    except Exception as exc:
        logger.warning("ANEEL API unavailable: {}", exc)
        return None

    if not data.get("success"):
        logger.warning("ANEEL API success=false")
        return None

    records = data.get("result", {}).get("records", [])
    parsed = _parse_records(records)
    if not parsed:
        logger.warning("ANEEL API returned no parsable records")
        return None

    return AneelCacheBundle(
        bandeiras=parsed,
        data_source="aneel_api",
        fetched_at=datetime.now().isoformat(timespec="seconds"),
        fallback_used=False,
    )


def _cache_valid(data: dict[str, Any]) -> bool:
    try:
        dt = datetime.fromisoformat(data["fetched_at"])
    except (KeyError, TypeError, ValueError):
        return False
    now = datetime.now()
    return dt.year == now.year and dt.month == now.month


def _load_disk_cache(path: str) -> AneelCacheBundle | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        logger.warning("Failed to read ANEEL cache: {}", exc)
        return None

    if not _cache_valid(data):
        logger.debug("ANEEL cache expired for current month")
        return None

    try:
        raw = data.get("bandeiras", {})
        bandeiras = {key: (value[0], float(value[1])) for key, value in raw.items()}
    except Exception as exc:
        logger.warning("Failed to decode ANEEL cache payload: {}", exc)
        return None

    return AneelCacheBundle(
        bandeiras=bandeiras,
        data_source=data.get("source", "disk_cache"),
        fetched_at=data.get("fetched_at"),
        fallback_used=bool(data.get("fallback_used", False)),
    )


def _save_disk_cache(path: str, bundle: AneelCacheBundle) -> None:
    try:
        dirpath = os.path.dirname(path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        payload = {
            "fetched_at": bundle.fetched_at,
            "source": bundle.data_source,
            "fallback_used": bundle.fallback_used,
            "bandeiras": {key: list(value) for key, value in bundle.bandeiras.items()},
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("Failed to save ANEEL cache: {}", exc)


_memory: AneelCacheBundle | None = None
_memory_cache_path: str | None = None


def _fallback_bundle() -> AneelCacheBundle:
    return AneelCacheBundle(
        bandeiras=_FALLBACK.copy(),
        data_source="embedded_fallback",
        fetched_at=None,
        fallback_used=True,
    )


def _load_bundle(
    cache_path: str,
    *,
    fetch_enabled: bool,
    allow_insecure_ssl: bool,
) -> AneelCacheBundle:
    cached = _load_disk_cache(cache_path)
    if cached is not None:
        return cached

    if fetch_enabled:
        fetched = _fetch_aneel(allow_insecure_ssl=allow_insecure_ssl)
        if fetched is not None:
            _save_disk_cache(cache_path, fetched)
            return fetched

    logger.warning(
        "Using embedded ANEEL fallback values. External source unavailable or disabled."
    )
    return _fallback_bundle()


def _get_bundle(
    cache_path: str,
    *,
    fetch_enabled: bool,
    allow_insecure_ssl: bool,
) -> AneelCacheBundle:
    global _memory, _memory_cache_path
    if _memory is None or _memory_cache_path != cache_path:
        _memory = _load_bundle(
            cache_path,
            fetch_enabled=fetch_enabled,
            allow_insecure_ssl=allow_insecure_ssl,
        )
        _memory_cache_path = cache_path
    return _memory


def resolve_bandeira(
    date: datetime,
    cache_path: str = _DEFAULT_CACHE,
    *,
    fetch_enabled: bool = True,
    allow_insecure_ssl: bool = False,
) -> AneelFlagResolution:
    bundle = _get_bundle(
        cache_path,
        fetch_enabled=fetch_enabled,
        allow_insecure_ssl=allow_insecure_ssl,
    )
    key = date.strftime("%Y-%m")
    bandeira, adicional = bundle.bandeiras.get(key, _DEFAULT)
    return AneelFlagResolution(
        date_key=key,
        bandeira=bandeira,
        adicional_brl=adicional,
        data_source=bundle.data_source,
        fetched_at=bundle.fetched_at,
        fallback_used=bundle.fallback_used,
        cache_path=cache_path,
    )


def get_bandeira(
    date: datetime,
    cache_path: str = _DEFAULT_CACHE,
    *,
    fetch_enabled: bool = True,
    allow_insecure_ssl: bool = False,
) -> tuple[str, float]:
    resolution = resolve_bandeira(
        date,
        cache_path=cache_path,
        fetch_enabled=fetch_enabled,
        allow_insecure_ssl=allow_insecure_ssl,
    )
    logger.debug(
        "Bandeira {}: {} (+R$ {:.5f}/kWh) source={} fallback={}",
        resolution.date_key,
        resolution.bandeira,
        resolution.adicional_brl,
        resolution.data_source,
        resolution.fallback_used,
    )
    return resolution.bandeira, resolution.adicional_brl


def invalidate_cache() -> None:
    global _memory, _memory_cache_path
    _memory = None
    _memory_cache_path = None
