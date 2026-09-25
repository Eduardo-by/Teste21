"""Coleta de negócios de Palmas-TO pela Google Places API (New) — Text Search.

Uso:
    export GOOGLE_MAPS_API_KEY="sua-chave"
    python api_places.py                         # todas as categorias
    python api_places.py -c restaurante pizzaria # só algumas
    python api_places.py --max-requisicoes 200   # teto de gasto

Cada busca devolve no máximo 60 resultados (3 páginas de 20). Para não perder
locais, a área é dividida em quadrantes: quando um quadrante "lota" (60
resultados), ele é subdividido em 4 e pesquisado de novo.

As respostas ficam em cache (cache_api.json), então rodar de novo não gasta
requisições com buscas já feitas.
"""

import argparse
import hashlib
import json
import os
import sys
import time

import requests

import config
from leads import Colecao, Lead, exportar, na_cidade

URL = "https://places.googleapis.com/v1/places:searchText"
CAMPOS = ",".join([
    "places.id", "places.displayName", "places.formattedAddress",
    "places.nationalPhoneNumber", "places.internationalPhoneNumber",
    "places.websiteUri", "places.rating", "places.userRatingCount",
    "places.businessStatus", "places.primaryTypeDisplayName",
    "places.googleMapsUri", "places.location", "nextPageToken",
])
MAX_PAGINAS = 3
ARQ_CACHE = "cache_api.json"


class LimiteAtingido(Exception):
    pass


class Cliente:
    def __init__(self, chave: str, max_requisicoes: int):
        self.sessao = requests.Session()
        self.sessao.headers.update({
            "X-Goog-Api-Key": chave,
            "X-Goog-FieldMask": CAMPOS,
            "Content-Type": "application/json",
        })
        self.max_requisicoes = max_requisicoes
        self.requisicoes = 0
        self.cache = self._carregar_cache()

    @staticmethod
    def _carregar_cache() -> dict:
        try:
            with open(ARQ_CACHE, encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def salvar_cache(self):
        with open(ARQ_CACHE, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False)

    def _post(self, corpo: dict) -> dict:
        if self.requisicoes >= self.max_requisicoes:
            raise LimiteAtingido
        for tentativa in range(5):
            self.requisicoes += 1
            r = self.sessao.post(URL, json=corpo, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** tentativa)
                continue
            sys.exit(f"Erro da API ({r.status_code}): {r.text[:500]}")
        sys.exit("A API continuou falhando após 5 tentativas.")

    def buscar(self, termo: str, ret: tuple) -> tuple[list[dict], bool]:
        """Retorna (lugares, lotou). 'lotou' indica que havia mais de 60 resultados."""
        k = hashlib.sha1(json.dumps([termo, ret]).encode()).hexdigest()
        if k in self.cache:
            c = self.cache[k]
            return c["lugares"], c["lotou"]

        s, o, n, l = ret
        corpo = {
            "textQuery": termo,
            "languageCode": "pt-BR",
            "regionCode": "BR",
            "pageSize": 20,
            "locationRestriction": {"rectangle": {
                "low": {"latitude": s, "longitude": o},
                "high": {"latitude": n, "longitude": l},
            }},
        }
        lugares, token = [], None
        for _ in range(MAX_PAGINAS):
            if token:
                corpo["pageToken"] = token
            dados = self._post(corpo)
            lugares += dados.get("places", [])
            token = dados.get("nextPageToken")
            if not token:
                break
        lotou = bool(token)
        self.cache[k] = {"lugares": lugares, "lotou": lotou}
        return lugares, lotou


def dividir(ret: tuple) -> list[tuple]:
    s, o, n, l = ret
    ml, mo = (s + n) / 2, (o + l) / 2
    return [(s, o, ml, mo), (s, mo, ml, l), (ml, o, n, mo), (ml, mo, n, l)]


def grade_inicial(ret: tuple, passo: float) -> list[tuple]:
    s, o, n, l = ret
    celulas, lat = [], s
    while lat < n:
        lon = o
        while lon < l:
            celulas.append((lat, lon, min(lat + passo, n), min(lon + passo, l)))
            lon += passo
        lat += passo
    return celulas


def para_lead(p: dict, busca: str) -> Lead:
    loc = p.get("location", {})
    return Lead(
        nome=p.get("displayName", {}).get("text", ""),
        categoria=p.get("primaryTypeDisplayName", {}).get("text", ""),
        endereco=p.get("formattedAddress", ""),
        telefone=p.get("nationalPhoneNumber") or p.get("internationalPhoneNumber", ""),
        site=p.get("websiteUri", ""),
        nota=p.get("rating"),
        avaliacoes=p.get("userRatingCount", 0),
        status=p.get("businessStatus", ""),
        latitude=loc.get("latitude"),
        longitude=loc.get("longitude"),
        link_maps=p.get("googleMapsUri", ""),
        place_id=p.get("id", ""),
        busca=busca,
    )


def coletar(cliente: Cliente, termo: str, ret: tuple, colecao: Colecao, tam_min: float) -> int:
    lugares, lotou = cliente.buscar(termo, ret)
    if lotou and (ret[2] - ret[0]) > tam_min:
        return sum(coletar(cliente, termo, sub, colecao, tam_min) for sub in dividir(ret))
    novos = 0
    for p in lugares:
        novos += colecao.adicionar(para_lead(p, termo))
    return novos


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-c", "--categorias", nargs="+", default=config.CATEGORIAS)
    ap.add_argument("--max-requisicoes", type=int, default=1000,
                    help="teto de chamadas à API nesta execução (padrão: 1000)")
    ap.add_argument("--passo", type=float, default=0.05,
                    help="tamanho inicial dos quadrantes em graus (0.05 ≈ 5,5 km)")
    ap.add_argument("--incluir-fechados", action="store_true",
                    help="manter locais fechados permanentemente")
    ap.add_argument("--incluir-fora", action="store_true",
                    help="manter locais cujo endereço não é de Palmas")
    ap.add_argument("-o", "--saida", default="leads_palmas_api")
    args = ap.parse_args()

    chave = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not chave:
        sys.exit("Defina a variável GOOGLE_MAPS_API_KEY com sua chave da Places API.")

    cliente = Cliente(chave, args.max_requisicoes)
    colecao = Colecao()
    celulas = grade_inicial(config.AREA_PALMAS, args.passo)
    tam_min = args.passo / 8

    try:
        for i, termo in enumerate(args.categorias, 1):
            antes = cliente.requisicoes
            novos = sum(coletar(cliente, termo, c, colecao, tam_min) for c in celulas)
            print(f"[{i}/{len(args.categorias)}] {termo}: +{novos} novos "
                  f"(total {len(colecao)}, {cliente.requisicoes - antes} requisições)")
            cliente.salvar_cache()
    except LimiteAtingido:
        print(f"\nTeto de {args.max_requisicoes} requisições atingido. "
              "Rode de novo para continuar (o que já foi buscado está em cache).")
    except KeyboardInterrupt:
        print("\nInterrompido. Salvando o que foi coletado...")
    finally:
        cliente.salvar_cache()

    leads = [l for l in colecao.ordenados()
             if (args.incluir_fora or na_cidade(l, config.CIDADE))
             and (args.incluir_fechados or l.status != "CLOSED_PERMANENTLY")]
    for arq in exportar(leads, args.saida):
        print("Salvo:", arq)
    print(f"{len(leads)} leads | {cliente.requisicoes} requisições nesta execução")


if __name__ == "__main__":
    main()
