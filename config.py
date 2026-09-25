"""Configuração da busca: área de Palmas-TO e categorias de negócios."""

CIDADE = "Palmas"
UF = "TO"

# Retângulo que cobre a área urbana de Palmas (Plano Diretor, Taquaralto,
# Aurenys, Taquari e arredores). Formato: (sul, oeste, norte, leste).
AREA_PALMAS = (-10.37, -48.39, -10.12, -48.26)

# Termos de busca. O Google não tem um "listar tudo", então cobrimos a cidade
# pesquisando várias categorias. Edite à vontade.
CATEGORIAS = [
    # Alimentação
    "restaurante", "lanchonete", "pizzaria", "hamburgueria", "padaria",
    "cafeteria", "bar", "sorveteria", "açaí", "confeitaria", "marmitaria",
    "churrascaria", "comida japonesa", "distribuidora de bebidas",
    # Comércio
    "loja de roupas", "loja de calçados", "loja de móveis",
    "material de construção", "loja de eletrônicos", "loja de celulares",
    "loja de cosméticos", "perfumaria", "joalheria", "ótica",
    "loja de presentes", "papelaria", "floricultura", "loja de brinquedos",
    "loja de artigos esportivos", "supermercado", "mercearia", "farmácia",
    "pet shop", "autopeças", "loja de informática", "loja de variedades",
    # Serviços
    "salão de beleza", "barbearia", "clínica de estética", "manicure",
    "academia", "clínica odontológica", "clínica médica", "fisioterapia",
    "clínica veterinária", "oficina mecânica", "lava jato", "auto escola",
    "imobiliária", "contabilidade", "escritório de advocacia", "escola",
    "curso de idiomas", "gráfica", "lavanderia", "assistência técnica",
    "hotel", "pousada", "buffet", "fotógrafo", "agência de viagens",
    "vidraçaria", "serralheria", "marcenaria", "estúdio de tatuagem",
]
