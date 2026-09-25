# Leads de Palmas-TO no Google Maps

Coleta lojas, restaurantes e outros negócios de Palmas-TO no Google Maps e gera uma planilha de prospecção para vender sites e sistemas.

## O que sai na planilha

`leads_palmas_*.xlsx` (e `.csv` com separador `;`, que o Excel abre direto). A planilha já vem ordenada por prioridade:

| Prioridade | Significado |
|---|---|
| **A** (verde) | **Sem site e com telefone.** São os melhores alvos. |
| **B** (amarelo) | Tem só Instagram, Facebook, Linktree ou iFood, ou está sem site e sem telefone. |
| **C** (cinza) | Já tem site. Dá para oferecer sistema, redesign ou loja virtual. |

Dentro de cada prioridade, quem tem mais avaliações vem primeiro. Em geral são os negócios mais movimentados, com mais chance de ter orçamento.

Colunas: nome, categoria, telefone, link de WhatsApp (gerado quando o número é celular), site, endereço, nota, nº de avaliações, link do Maps e coordenadas. A aba **Resumo** mostra quantos leads há em cada prioridade.

## Opção 1: API oficial do Google (recomendada)

É mais rápida, é estável e está dentro das regras do Google.

1. Crie um projeto no [Google Cloud Console](https://console.cloud.google.com/), ative a **Places API (New)** e gere uma chave de API. Precisa cadastrar um cartão de cobrança.
2. Rode:

```bash
pip install -r requirements.txt
export GOOGLE_MAPS_API_KEY="sua-chave"      # Windows: set GOOGLE_MAPS_API_KEY=sua-chave
python api_places.py
```

**Custo.** Telefone e site ficam no nível de preço mais alto da Text Search. Confira os preços atuais e a cota gratuita mensal em <https://developers.google.com/maps/billing-and-pricing/pricing>. Para você não levar susto, o script para em **1000 requisições** por execução (`--max-requisicoes`). Tudo o que já foi buscado fica em `cache_api.json`, então rodar de novo continua de onde parou sem pagar outra vez. Para um teste barato, rode antes só algumas categorias:

```bash
python api_places.py -c restaurante pizzaria --max-requisicoes 50
```

## Opção 2: raspagem com navegador (grátis)

Não precisa de chave. O Playwright abre o Google Maps, pesquisa cada categoria, rola a lista e entra em cada local.

```bash
pip install -r requirements.txt
playwright install chromium
python raspar_maps.py            # use --mostrar para ver o navegador
```

- É lento: cerca de 3 s por local, então a cidade inteira leva algumas horas. O progresso é salvo a cada local em `progresso_raspagem.json`. Se cair, rode de novo que ele continua.
- O Maps mostra no máximo cerca de 120 resultados por busca. Por isso existem muitas categorias em `config.py`.
- Automatizar o site vai contra os Termos de Serviço do Google. O Google pode mostrar CAPTCHA ou bloquear, e se o layout mudar os seletores em `raspar_maps.py` precisam ser atualizados.

## Personalizar

Em `config.py` ficam a lista de **categorias** pesquisadas e o **retângulo** da cidade. Por padrão os scripts descartam locais fechados permanentemente e endereços fora de Palmas. Use `--incluir-fechados` e `--incluir-fora` para mantê-los.

## Boas práticas na prospecção

- São dados públicos de empresas, mas a LGPD continua valendo. Aborde de forma individual, identifique-se e retire da lista quem pedir.
- **Não dispare mensagens em massa no WhatsApp.** O WhatsApp bane números que fazem isso. Mande poucas mensagens por dia, personalizadas. Por exemplo: "vi que a Pizzaria X tem 1.200 avaliações no Google mas ainda não tem site…".
