"""Classifica a presença digital a partir da URL e, se preciso, de uma página.

Rede social e construtor gratuito saem só do endereço. Domínio próprio recebe
uma requisição à página inicial. Falha, bloqueio ou rede interna ficam como
site próprio: a importação segue.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

MAX_VISITAS = 60
LIMITE_BYTES = 100_000
REDIRECIONA = {301, 302, 303, 307, 308}
AGENTE = "RebelattoBot/1.0 (+https://rebelatto.tech)"

SOCIAIS = (
    ("instagram.com", "Instagram"),
    ("facebook.com", "Facebook"),
    ("fb.com", "Facebook"),
    ("fb.me", "Facebook"),
    ("linktr.ee", "Linktree"),
    ("linktree.com", "Linktree"),
    ("tiktok.com", "TikTok"),
    ("youtube.com", "YouTube"),
    ("youtu.be", "YouTube"),
    ("wa.me", "WhatsApp"),
    ("whatsapp.com", "WhatsApp"),
    ("t.me", "Telegram"),
)

CONSTRUTORES = (
    ("wixsite.com", "Wix"),
    ("wordpress.com", "WordPress.com"),
    ("blogspot.com", "Blogger"),
    ("blogger.com", "Blogger"),
    ("negocio.site", "construtor gratuito"),
    ("godaddysites.com", "construtor gratuito"),
    ("webnode.page", "construtor gratuito"),
    ("webnode.com", "construtor gratuito"),
    ("weebly.com", "construtor gratuito"),
    ("square.site", "construtor gratuito"),
    ("carrd.co", "construtor gratuito"),
    ("mystrikingly.com", "construtor gratuito"),
    ("jimdofree.com", "construtor gratuito"),
    ("jimdosite.com", "construtor gratuito"),
    ("canva.site", "construtor gratuito"),
    ("sites.google.com", "construtor gratuito"),
    ("notion.site", "construtor gratuito"),
    ("myshopify.com", "Shopify"),
    ("webflow.io", "construtor gratuito"),
    ("cargo.site", "construtor gratuito"),
)

MARCAS_HTML = (
    ("wixstatic.com", "Wix"),
    ("parastorage.com", "Wix"),
    ("squarespace-cdn.com", "Squarespace"),
    ("squarespace.com", "Squarespace"),
    ("cdn.shopify.com", "Shopify"),
    ("website-files.com", "construtor gratuito"),
)

VENDA = (
    "domain for sale",
    "buy this domain",
    "this domain is for sale",
    "dominio a venda",
    "compre este dominio",
    "webpage is parked",
    "domain is parked",
    "hugedomains",
    "sedoparking",
    "afternic",
)

OBRA = (
    "em construcao",
    "under construction",
    "coming soon",
    "site em construcao",
)


class UrlInsegura(Exception):
    pass


@dataclass(frozen=True)
class Presenca:
    categoria: str
    detalhe: str
    visitou: bool = False


def normalizar(website: str) -> str:
    texto = (website or "").strip()
    if not texto:
        return ""
    if not re.match(r"^https?://", texto, re.I):
        texto = "https://" + texto
    return texto


def host_de(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def _casa_host(host: str, dominio: str) -> bool:
    return host == dominio or host.endswith("." + dominio)


def _rotulo(host: str, tabela: tuple[tuple[str, str], ...]) -> str:
    for dominio, nome in tabela:
        if _casa_host(host, dominio):
            return nome
    return ""


def classificar_por_url(website: str) -> Presenca | None:
    """None pede visita. O resto já está decidido pelo endereço."""
    url = normalizar(website)
    if not url:
        return Presenca("sem_site", "")
    host = host_de(url)
    if not host:
        return Presenca("site_proprio", "não abriu")
    social = _rotulo(host, SOCIAIS)
    if social:
        return Presenca("rede_social", social)
    construtor = _rotulo(host, CONSTRUTORES)
    if construtor:
        return Presenca("site_fraco", construtor)
    return None


def _sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(caractere for caractere in base if not unicodedata.combining(caractere))


def _texto(html: str) -> str:
    sem = re.sub(r"(?is)<(script|style|noscript)\b[^>]*>.*?</\1>", " ", html)
    sem = re.sub(r"(?s)<[^>]+>", " ", sem)
    sem = re.sub(r"&\w+;", " ", sem)
    return re.sub(r"\s+", " ", sem).strip()


def _titulo(html: str) -> str:
    achado = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    if not achado:
        return ""
    return re.sub(r"\s+", " ", achado.group(1)).strip()


def _titulo_fraco(titulo: str, url: str) -> bool:
    if not titulo:
        return True
    comparavel = _sem_acento(titulo)
    host = host_de(url)
    if host and host in comparavel:
        return True
    return comparavel in {"home", "welcome", "index", "inicio", "untitled"}


def _wordpress(html: str) -> bool:
    return any(
        marca in html
        for marca in ("wp-content", "wp-includes", "/wp-json", 'content="wordpress')
    )


def classificar_resposta(
    url_final: str,
    status: int,
    html: str,
    *,
    parece_html: bool = True,
) -> Presenca:
    por_url = classificar_por_url(url_final)
    if por_url is not None and por_url.categoria != "sem_site":
        return Presenca(por_url.categoria, por_url.detalhe, True)
    if status >= 400 or status <= 0 or not parece_html:
        return Presenca("site_proprio", "não abriu", True)

    pagina = _sem_acento(html)
    if any(frase in pagina for frase in VENDA):
        return Presenca("sem_site", "domínio à venda", True)
    if any(frase in pagina for frase in OBRA):
        return Presenca("sem_site", "em construção", True)
    for marca, nome in MARCAS_HTML:
        if marca in pagina:
            return Presenca("site_fraco", nome, True)

    texto = _texto(html)
    if _wordpress(pagina) and len(texto) < 500:
        return Presenca("site_fraco", "WordPress com pouco conteúdo", True)
    if _wordpress(pagina):
        return Presenca("site_proprio", "WordPress", True)
    if len(texto) < 40 and _titulo_fraco(_titulo(html), url_final):
        return Presenca("sem_site", "página vazia", True)
    return Presenca("site_proprio", "página no ar", True)


def url_publica(url: str) -> bool:
    partes = urlparse(url)
    if partes.scheme not in {"http", "https"}:
        return False
    if partes.username or partes.password:
        return False
    host = partes.hostname
    if not host:
        return False
    host = host.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal")):
        return False
    try:
        endereco = ipaddress.ip_address(host)
    except ValueError:
        endereco = None
    if endereco is not None:
        return bool(endereco.is_global)
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    if not infos:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            return False
    return True


def _parece_html(tipo: str) -> bool:
    if not tipo:
        return True
    return any(parte in tipo for parte in ("html", "text/", "xml"))


def _corpo(resp) -> str:
    partes: list[str] = []
    total = 0
    for pedaco in resp.iter_text():
        partes.append(pedaco)
        total += len(pedaco)
        if total >= LIMITE_BYTES:
            break
    return "".join(partes)[:LIMITE_BYTES]


def _ler(http, url: str) -> tuple[str, int, str, bool]:
    atual = url
    for _ in range(4):
        if not url_publica(atual):
            raise UrlInsegura()
        with http.stream("GET", atual) as resp:
            if resp.status_code in REDIRECIONA:
                destino = urljoin(atual, resp.headers.get("location") or "")
                if not destino or destino == atual:
                    return atual, resp.status_code, "", False
                atual = destino
                continue
            tipo = (resp.headers.get("content-type") or "").lower()
            parece = _parece_html(tipo)
            if not parece:
                return atual, resp.status_code, "", False
            return atual, resp.status_code, _corpo(resp), True
    raise UrlInsegura()


def _abrir(cliente):
    if cliente is not None:
        return cliente
    return httpx.Client(
        timeout=httpx.Timeout(4.0),
        follow_redirects=False,
        headers={
            "User-Agent": AGENTE,
            "Accept": "text/html,application/xhtml+xml",
        },
    )


def visitar(url: str, *, cliente=None) -> Presenca:
    try:
        alvo = normalizar(url)
        if not alvo:
            return Presenca("sem_site", "")
        if not url_publica(alvo):
            return Presenca("site_proprio", "não abriu", True)
        with _abrir(cliente) as http:
            final, status, html, parece = _ler(http, alvo)
        return classificar_resposta(final, status, html, parece_html=parece)
    except UrlInsegura:
        return Presenca("site_proprio", "não abriu", True)
    except (httpx.HTTPError, OSError, UnicodeError, ValueError):
        return Presenca("site_proprio", "não abriu", True)


def visitar_varios(urls: list[str]) -> dict[str, Presenca]:
    unicos: list[str] = []
    vistos: set[str] = set()
    for url in urls:
        if url and url not in vistos:
            vistos.add(url)
            unicos.append(url)
    limite = unicos[:MAX_VISITAS]
    resto = unicos[MAX_VISITAS:]
    saida = {url: Presenca("site_proprio", "não verificado") for url in resto}
    if not limite:
        return saida
    with ThreadPoolExecutor(max_workers=8) as pool:
        futuros = {pool.submit(visitar, url): url for url in limite}
        for futuro in as_completed(futuros):
            url = futuros[futuro]
            try:
                saida[url] = futuro.result()
            except Exception:
                saida[url] = Presenca("site_proprio", "não abriu", True)
    return saida
