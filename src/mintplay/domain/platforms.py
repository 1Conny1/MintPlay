"""Detección y normalización centralizada de plataformas por dominio y extractor."""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

PLATAFORMA_GENERICA = "Otro sitio"

VALORES_GENERICOS = {
    "",
    "otro sitio",
    "other site",
    "generic",
    "html5mediaembed",
    "direct",
}

# Mapa ordenado de plataformas canónicas y sus dominios raíz admitidos.
# La comparación se hace únicamente por coincidencia exacta de host o subdominio real (.dominio).
DOMINIOS_PLATAFORMAS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Facebook", ("facebook.com", "fb.watch", "fb.com")),
    ("YouTube", ("youtube.com", "youtu.be", "youtube-nocookie.com")),
    ("Instagram", ("instagram.com", "instagr.am")),
    ("TikTok", ("tiktok.com",)),
    ("X / Twitter", ("twitter.com", "x.com", "t.co")),
    ("Vimeo", ("vimeo.com",)),
    ("Twitch", ("twitch.tv",)),
    ("Reddit", ("reddit.com", "redd.it")),
    ("SoundCloud", ("soundcloud.com",)),
    ("Dailymotion", ("dailymotion.com", "dai.ly")),
    ("Bilibili", ("bilibili.com", "b23.tv")),
)

PREFIJOS_EXTRACTOR: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Facebook", ("facebook", "fb")),
    ("YouTube", ("youtube", "yt")),
    ("Instagram", ("instagram",)),
    ("TikTok", ("tiktok",)),
    ("X / Twitter", ("twitter", "x")),
    ("Vimeo", ("vimeo",)),
    ("Twitch", ("twitch",)),
    ("Reddit", ("reddit",)),
    ("SoundCloud", ("soundcloud",)),
    ("Dailymotion", ("dailymotion",)),
    ("Bilibili", ("bilibili", "bili")),
)


def _coincide_host_o_subdominio(host: str, dominio_base: str) -> bool:
    """Verifica si host es exactamente dominio_base o un subdominio real (.dominio_base)."""
    return host == dominio_base or host.endswith(f".{dominio_base}")


def extraer_host_normalizado(url: str) -> Optional[str]:
    """Extrae y normaliza el host en minúsculas sin puerto desde una URL HTTP/HTTPS."""
    url_limpia = (url or "").strip()
    if not url_limpia:
        return None

    esquema_bajo = url_limpia.lower()
    if not (esquema_bajo.startswith("http://") or esquema_bajo.startswith("https://")):
        return None

    try:
        parsed = urlparse(url_limpia)
        host = (parsed.hostname or "").strip().lower().rstrip(".")
        return host if host else None
    except Exception:
        return None


def detectar_plataforma_por_url(url: str) -> Optional[str]:
    """Reconoce la plataforma a partir del dominio o subdominio real de la URL.

    Devuelve el nombre canónico (ej. 'Facebook', 'YouTube') o None si no corresponde
    a una plataforma conocida o la URL no es válida.
    """
    host = extraer_host_normalizado(url)
    if not host:
        return None

    for nombre_plataforma, dominios in DOMINIOS_PLATAFORMAS:
        for dom in dominios:
            if _coincide_host_o_subdominio(host, dom):
                return nombre_plataforma

    return None


def normalizar_nombre_plataforma(valor: Optional[str]) -> Optional[str]:
    """Normaliza un nombre de plataforma o extractor_key de yt-dlp a su etiqueta canónica.

    Devuelve None si el valor es vacío o genérico ('Generic', 'Otro sitio', 'Other site').
    """
    limpio = (valor or "").strip()
    if not limpio:
        return None

    bajo = limpio.lower()
    if bajo in VALORES_GENERICOS:
        return None

    # Si ya coincide con una plataforma canónica
    for nombre_canonico, _ in DOMINIOS_PLATAFORMAS:
        if bajo == nombre_canonico.lower():
            return nombre_canonico

    # Verificar por prefijo/familia de extractor de yt-dlp (ej. FacebookReel, YoutubeTab)
    for nombre_canonico, prefijos in PREFIJOS_EXTRACTOR:
        for pref in prefijos:
            if bajo == pref or bajo.startswith(pref):
                return nombre_canonico

    return limpio


def resolver_plataforma(
    url: str = "",
    extractor_key: Optional[str] = None,
    plataforma_actual: Optional[str] = None,
) -> str:
    """Resuelve la plataforma de forma consistente para formulario, cola e historial.

    Prioriza:
    1. El extractor específico de yt-dlp (si no es genérico).
    2. La plataforma conocida previamente asignada (sin degradarla a 'Otro sitio').
    3. El dominio/subdominio real de la URL (cuando la plataforma previa era vacía o genérica).
    4. 'Otro sitio' como valor genérico interno.
    """
    desde_extractor = normalizar_nombre_plataforma(extractor_key)
    if desde_extractor:
        return desde_extractor

    desde_actual = normalizar_nombre_plataforma(plataforma_actual)
    if desde_actual:
        return desde_actual

    desde_url = detectar_plataforma_por_url(url)
    if desde_url:
        return desde_url

    return PLATAFORMA_GENERICA
