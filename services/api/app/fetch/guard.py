"""Egress-guard против SSRF.

Сервер фетчит пользовательские URL (источники, тест источника). Без фильтрации
тенант мог бы направить fetch на loopback/link-local/private/reserved адрес
(например 169.254.169.254 — облачные метаданные) и через ответ/ошибку прощупать
внутреннюю сеть. Guard применяется на входе каждого fetch пользовательского URL.
"""

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

_MAX_REDIRECTS = 5


class BlockedUrlError(Exception):
    """URL имеет недопустимую схему или резолвится в непубличный адрес."""


def _is_public_ip(ip_text: str) -> bool:
    ip = ipaddress.ip_address(ip_text)
    return ip.is_global and not ip.is_multicast and not ip.is_reserved


def _resolve_public(url: str) -> tuple[str, str]:
    """Провалидировать схему/хост и зарезолвить хост, вернув (host, pinned_ip).

    ВСЕ резолвнутые адреса обязаны быть публичными; на коннект отдаём первый (pinned), чтобы
    http-клиент не резолвил хост заново — это закрывает DNS-rebinding/TOCTOU (публичный IP в
    момент проверки, приватный в момент коннекта).
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise BlockedUrlError("blocked_scheme")
    host = parsed.hostname
    if not host:
        raise BlockedUrlError("no_host")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise BlockedUrlError("dns_error") from exc
    if not infos:
        raise BlockedUrlError("dns_error")
    addresses = [info[4][0] for info in infos]
    for address in addresses:
        if not _is_public_ip(address):
            raise BlockedUrlError("blocked_target")
    return host, addresses[0]


def assert_public_url(url: str) -> None:
    """Пропустить только http/https на хост, резолвящийся исключительно в публичные IP."""
    _resolve_public(url)


def safe_get(url: str, *, headers: dict[str, str], timeout: float) -> httpx.Response:
    """GET с валидацией и IP-pinning КАЖДОГО редирект-хопа против egress-guard.

    Автоследование редиректов выключено (иначе редирект на приватный адрес обходит предпроверку
    начального URL). Коннект идёт на зарезолвленный публичный IP при сохранении Host и TLS-SNI =
    хостнейм, поэтому http-клиент не резолвит хост повторно — DNS-rebinding закрыт.
    """
    current = httpx.URL(url)
    with httpx.Client(follow_redirects=False, timeout=timeout, headers=headers) as client:
        for _ in range(_MAX_REDIRECTS + 1):
            host, ip = _resolve_public(str(current))
            pinned = current.copy_with(host=ip)
            host_header = host if current.port is None else f"{host}:{current.port}"
            request = client.build_request(
                "GET",
                pinned,
                headers={"Host": host_header},
                extensions={"sni_hostname": host},
            )
            response = client.send(request)
            location = response.headers.get("location")
            if response.is_redirect and location:
                current = current.join(location)
                continue
            return response
    raise BlockedUrlError("too_many_redirects")
