"""Raspagem do Google Maps com navegador (Playwright) — não precisa de chave.

Uso (na sua máquina):
    pip install -r requirements.txt
    playwright install chromium
    python raspar_maps.py                          # todas as categorias
    python raspar_maps.py -c restaurante barbearia # só algumas
    python raspar_maps.py --mostrar                # ver o navegador trabalhando

O progresso é salvo em progresso_raspagem.json a cada local visitado. Se cair
ou você interromper (Ctrl+C), é só rodar de novo que ele continua de onde parou.

Atenção: automatizar o site do Google Maps vai contra os Termos de Serviço do
Google, e o layout pode mudar e quebrar os seletores abaixo. Vá devagar para
não ser bloqueado.
"""

import argparse
import json
import random
import re
import time
from dataclasses import asdict
from urllib.parse import quote

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

import config
from leads import Colecao, Lead, exportar, na_cidade

ARQ_PROGRESSO = "progresso_raspagem.json"
FIM_DA_LISTA = ("Você chegou ao final da lista", "You've reached the end of the list")


def pausa(a=1.0, b=2.5):
    time.sleep(random.uniform(a, b))


def carregar_progresso() -> dict:
    try:
        with open(ARQ_PROGRESSO, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"leads": [], "visitados": [], "categorias_ok": []}


def salvar_progresso(prog: dict):
    with open(ARQ_PROGRESSO, "w", encoding="utf-8") as f:
        json.dump(prog, f, ensure_ascii=False)


def aceitar_cookies(page):
    for txt in ("Aceitar tudo", "Accept all"):
        botao = page.get_by_role("button", name=txt)
        if botao.count():
            botao.first.click()
            pausa()
            return


def id_do_link(href: str) -> str:
    m = re.search(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)", href)
    return m.group(1) if m else href.split("?")[0]


def listar_resultados(page, termo: str, limite: int) -> list[str]:
    url = f"https://www.google.com/maps/search/{quote(termo)}?hl=pt-BR"
    page.goto(url, wait_until="domcontentloaded")
    aceitar_cookies(page)
    try:
        page.wait_for_selector('div[role="feed"]', timeout=15000)
    except PWTimeout:
        # Busca com um único resultado abre direto a ficha do local.
        return [page.url] if "/maps/place/" in page.url else []

    feed = page.locator('div[role="feed"]')
    links, parado = [], 0
    while parado < 6 and len(links) < limite:
        feed.evaluate("el => el.scrollBy(0, el.scrollHeight)")
        pausa(1.2, 2.2)
        atuais = page.eval_on_selector_all(
            'div[role="feed"] a[href*="/maps/place/"]', "els => els.map(e => e.href)")
        parado = parado + 1 if len(atuais) == len(links) else 0
        links = list(dict.fromkeys(atuais))
        if any(page.get_by_text(t).count() for t in FIM_DA_LISTA):
            break
    return links[:limite]


def _texto(page, seletor: str) -> str:
    el = page.locator(seletor).first
    return el.inner_text().strip() if el.count() else ""


def _attr(page, seletor: str, attr: str) -> str:
    el = page.locator(seletor).first
    return (el.get_attribute(attr) or "").strip() if el.count() else ""


def ler_local(page, href: str, termo: str) -> Lead | None:
    page.goto(href, wait_until="domcontentloaded")
    try:
        page.wait_for_selector("h1", timeout=15000)
    except PWTimeout:
        return None
    pausa(0.8, 1.5)

    endereco = _attr(page, 'button[data-item-id="address"]', "aria-label")
    endereco = re.sub(r"^(Endereço|Address):\s*", "", endereco)
    telefone = _attr(page, 'button[data-item-id^="phone:tel:"]', "data-item-id").replace("phone:tel:", "")

    nota_txt = _texto(page, 'div.F7nice span[aria-hidden="true"]')
    nota = float(nota_txt.replace(",", ".")) if re.fullmatch(r"\d[.,]\d", nota_txt) else None
    aval_txt = _attr(page, 'div.F7nice span[aria-label*="avalia"], div.F7nice span[aria-label*="review"]', "aria-label")
    avaliacoes = int(re.sub(r"\D", "", aval_txt) or 0)

    coords = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", page.url) or re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", href)
    fechado = page.get_by_text(re.compile("Fechado permanentemente|Permanently closed")).count() > 0

    return Lead(
        nome=_texto(page, "h1"),
        categoria=_texto(page, 'button[jsaction*="category"]'),
        endereco=endereco,
        telefone=telefone,
        site=_attr(page, 'a[data-item-id="authority"]', "href"),
        nota=nota,
        avaliacoes=avaliacoes,
        status="CLOSED_PERMANENTLY" if fechado else "",
        latitude=float(coords.group(1)) if coords else None,
        longitude=float(coords.group(2)) if coords else None,
        link_maps=href.split("?")[0],
        place_id=id_do_link(href),
        busca=termo,
    )


def abrir_navegador(pw, headless: bool):
    """Usa o Chromium do Playwright; se não estiver baixado, cai para Edge/Chrome instalados."""
    try:
        return pw.chromium.launch(headless=headless)
    except PlaywrightError as e:
        if "Executable doesn't exist" not in str(e):
            raise
    for canal in ("msedge", "chrome"):
        try:
            nav = pw.chromium.launch(channel=canal, headless=headless)
            print(f"Usando o navegador instalado: {canal}")
            return nav
        except PlaywrightError:
            continue
    raise SystemExit("Nenhum navegador encontrado. Rode: python -m playwright install chromium")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-c", "--categorias", nargs="+", default=config.CATEGORIAS)
    ap.add_argument("--limite-por-busca", type=int, default=200,
                    help="máximo de locais por categoria (o Maps costuma parar em ~120)")
    ap.add_argument("--mostrar", action="store_true", help="abrir o navegador visível")
    ap.add_argument("--incluir-fechados", action="store_true")
    ap.add_argument("--incluir-fora", action="store_true",
                    help="manter locais cujo endereço não é de Palmas")
    ap.add_argument("-o", "--saida", default="leads_palmas_maps")
    args = ap.parse_args()

    prog = carregar_progresso()
    colecao = Colecao()
    for d in prog["leads"]:
        colecao.adicionar(Lead(**d))
    visitados = set(prog["visitados"])

    with sync_playwright() as pw:
        nav = abrir_navegador(pw, headless=not args.mostrar)
        ctx = nav.new_context(locale="pt-BR", viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        try:
            for i, cat in enumerate(args.categorias, 1):
                if cat in prog["categorias_ok"]:
                    continue
                termo = f"{cat} em {config.CIDADE} - {config.UF}"
                links = listar_resultados(page, termo, args.limite_por_busca)
                print(f"[{i}/{len(args.categorias)}] {cat}: {len(links)} resultados")
                for j, href in enumerate(links, 1):
                    pid = id_do_link(href)
                    if pid in visitados:
                        continue
                    try:
                        lead = ler_local(page, href, cat)
                    except Exception as e:  # um local com problema não deve parar tudo
                        print(f"   erro em {href[:80]}: {e}")
                        continue
                    visitados.add(pid)
                    if lead:
                        colecao.adicionar(lead)
                        print(f"   {j}/{len(links)} {lead.nome} | {lead.telefone or '-'} | {lead.site or 'sem site'}")
                    prog["leads"] = [asdict(l) for l in colecao.ordenados()]
                    prog["visitados"] = sorted(visitados)
                    salvar_progresso(prog)
                    pausa()
                prog["categorias_ok"].append(cat)
                salvar_progresso(prog)
        except KeyboardInterrupt:
            print("\nInterrompido. Rode de novo para continuar.")
        finally:
            nav.close()

    leads = [l for l in colecao.ordenados()
             if (args.incluir_fora or na_cidade(l, config.CIDADE))
             and (args.incluir_fechados or l.status != "CLOSED_PERMANENTLY")]
    for arq in exportar(leads, args.saida):
        print("Salvo:", arq)
    print(f"{len(leads)} leads")


if __name__ == "__main__":
    main()
