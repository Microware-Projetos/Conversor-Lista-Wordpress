import pandas as pd
import json
import os
import logging
import time
import re
from duckduckgo_search import DDGS
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configuração do logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('plotter_imagens.log'),
        logging.StreamHandler()
    ]
)

CACHE_FILE = 'cache_plotter.json'

def carregar_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=5, min=10, max=120),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def buscar_imagem_hp(descricao):
    logging.info(f"Iniciando busca de imagem DuckDuckGo para: {descricao}")
    try:
        time.sleep(5)
        
        with DDGS() as ddgs:
            resultados = ddgs.images(descricao + " site:hp.com", max_results=1)
            for r in resultados:
                imagem_url = r["image"]
                logging.info(f"Imagem encontrada: {imagem_url}")
                return imagem_url
        logging.warning(f"Nenhuma imagem encontrada para: {descricao}")
        return None
    except Exception as e:
        if "Ratelimit" in str(e):
            logging.warning(f"Rate limit atingido para: {descricao}. Aguardando antes de tentar novamente...")
            time.sleep(30)
        logging.error(f"Erro ao buscar imagem para: {descricao} - {str(e)}")
        raise

def processar_plotter_data(arquivo_plotter):
    logging.info(f"Iniciando processamento do arquivo: {arquivo_plotter}")
    df_plotter = pd.read_excel(arquivo_plotter, engine='calamine', sheet_name='SP', header=5)
    
    # Lista de possíveis categorias
    categorias_validas = [
        "Mercado Técnico",
        "Mercado Técnico - Multifuncionais & Scanners",
        "Mercado Criativo / Comunicação Visual",
        "Acessórios"
    ]

    categoria_atual = None
    categorias = []

    for idx, row in df_plotter.iterrows():
        valor = str(row['PL']).strip()
        # Verifica se a linha é uma das categorias válidas
        if any(valor.startswith(cat) for cat in categorias_validas):
            categoria_atual = valor
            categorias.append(None)  # Linha de categoria, não é produto
        else:
            categorias.append(categoria_atual)

    # Adiciona a coluna ao DataFrame
    df_plotter['categoria'] = categorias

    # Remove as linhas que são apenas categorias (sem produto)
    df_limpo = df_plotter[df_plotter["PN"].notna()]
    lista_json = []
    cache = carregar_cache()
    logging.info(f"Cache carregado com {len(cache)} itens")

    total_produtos = len(df_limpo)
    produtos_com_imagem = 0
    produtos_sem_imagem = 0
   
    for index, row in df_limpo.iterrows():
        try:
            pn = str(row["PN"]).strip()
            descricao = row["descrição"]
            preco = row["valor total com impostos"]

            logging.info(f"Processando produto {index}/{total_produtos} - PN: {pn}")
        
            if row["categoria"] != "Acessório":
                if pn in cache:
                    imagem_url = cache[pn]
                    logging.info(f"Imagem encontrada no cache para PN: {pn}")
                else:
                    try:
                        imagem_url = buscar_imagem_hp(descricao)
                        if imagem_url:
                            cache[pn] = imagem_url
                            salvar_cache(cache)
                            logging.info(f"Nova imagem adicionada ao cache para PN: {pn} e cache salvo")
                        else:
                            logging.warning(f"Não foi possível encontrar imagem para PN: {pn}")
                    except Exception as e:
                        logging.error(f"Erro ao processar imagem para PN {pn}: {str(e)}")
                        imagem_url = None
                        # Continua o processamento mesmo com erro na busca da imagem

            if imagem_url:
                produtos_com_imagem += 1
            else:
                produtos_sem_imagem += 1
            
            #4% IMPORTADO, 12% E 18% NACIONAIS 
            leadtime = ""
            icms_sp = str(row["ICMS SP"]) if pd.notna(row["ICMS SP"]) else ""
            if "12" in icms_sp:
                leadtime = "local"
            elif "18" in icms_sp:
                leadtime = "local"
            else:
                leadtime = "importado"

            produto_data = {
                'name': descricao,
                'sku': pn,
                'short_description': descricao,
                'description': descricao,
                'price': preco / (1 - (20 / 100)) if preco is not None else None,
                'regular_price': preco / (1 - (20 / 100)) if preco is not None else None,
                'stock_quantity': 10,
                'attributes': processar_attributes(row, row["categoria"]),
                'meta_data': processar_fotos(row, imagem_url),
                'dimmensions': processar_dimmensions(row),
                'weight': processar_weight(row),
                'categories': processar_categories(row, row["categoria"]),
                'shipping_class': leadtime,
                "manage_stock": True,
            }
          
            lista_json.append(produto_data)
            
        except Exception as e:
            logging.error(f"Erro ao processar produto {pn}: {str(e)}")
            continue  # Continua para o próximo produto mesmo se houver erro

    logging.info(f"Processamento concluído:")
    logging.info(f"Total de produtos processados: {total_produtos}")
    logging.info(f"Produtos com imagem: {produtos_com_imagem}")
    logging.info(f"Produtos sem imagem: {produtos_sem_imagem}")
    print(f"Produtos processados: {len(lista_json)}")
    print(f"Logs detalhados disponíveis em: plotter_imagens.log")
    with open("lista_plotter_json.json", "w", encoding="utf-8") as f:
        json.dump(lista_json, f, ensure_ascii=False, indent=2)

    return lista_json

def processar_attributes(product, categoria):
    attributes = []
    
    if categoria == "Mercado Técnico":
        attributes.append({
            'id': 9,
            'options': [categoria],
            'visible': True
        })
        
        attributes.append({
        'id': 46,
        'options': [extrair_familia(product["descrição"])],
        'visible': True
         })
    elif categoria == "Mercado Técnico - Multifuncionais & Scanners":
        attributes.append({
            'id': 9,
            'options': ["Multifuncionais & Scanners"],
            'visible': True
        })
        
        attributes.append({
        'id': 46,
        'options': [extrair_familia(product["descrição"])],
        'visible': True
        })
    elif categoria == "Mercado Criativo / Comunicação Visual":
        attributes.append({
            'id': 9,
            'options': [categoria],
            'visible': True
        })
        
        attributes.append({
        'id': 46,
        'options': [extrair_familia(product["descrição"])],
        'visible': True
        })
    else:
        attributes.append({
            'id': 9,
            'options': ["Acessório e peças para impressoras"],
            'visible': True
        })
    

  
    attributes.append({
        'id': 45,
        'options': ["HP"],
        'visible': True
    })
    return attributes

def processar_categories(product, categoria):
        
    categories = []
    with open('HP/maps/categoriesWordpress.json', 'r') as f:
        categories_mapping = json.load(f)
    
    for category in categories_mapping:
        if category['name'] == "Impressora":
            categories.append({"id": category['id']})
            break
    
    # Garante que sempre tenha pelo menos uma categoria
    if not categories:
        # Adiciona "Acessório" como categoria padrão
        for category in categories_mapping:
            if category['name'] == "Acessório":
                categories.append({"id": category['id']})
                break

    return categories

def processar_fotos(product, imagem_url):
    if product["categoria"] != "Acessório":
        meta_data = [
            {
                "key": "_external_image_url",
                "value": imagem_url
            }
        ]
    else:
        meta_data = [
            {
                "key": "_external_image_url",
                "value": "https://eprodutos-integracao.microware.com.br/api/photos/image/67f94fefc26591a05fd049bd.png"
            }
        ]
    return meta_data

def processar_dimmensions(product):
    if product["categoria"] != "Acessório":
        if "24-in" in product["descrição"].lower() or "24in" in product["descrição"].lower():
            # Dimensões mínimas (L x P x A): 1013 x 440 x 285 mm 
            return {
                "length": 1013 / 10,
                "width": 440 / 10,
                "height": 285 / 10
            }
        elif "36-in" in product["descrição"].lower() or "36in" in product["descrição"].lower():
            # Embalagem 1575 x 570 x 650 mm
            return {
                "length": 1575 / 10,
                "width": 570 / 10,
                "height": 650 / 10
            }
        elif "44in" in product["descrição"].lower() or "44in" in product["descrição"].lower() or "42-in" in product["descrição"].lower() or "42in" in product["descrição"].lower():
            # 2280 x 735 x 1200 mm
            return {
                "length": 2280 / 10,
                "width": 735 / 10,
                "height": 1200 / 10
            }
        elif '64"' in product["descrição"].lower() or "64in" in product["descrição"].lower():
            #2800 x 750 x 1302 mm
            return {
                "length": 2800 / 10,
                "width": 750 / 10,
                "height": 1302 / 10
            }
        else:
            return {
                "length": 1575 / 10,
                "width": 570 / 10,
                "height": 650 / 10
            }
    else:
        return {
            "length": 91.00,
            "width": 91.00,
            "height": 91.00
        }

def processar_weight(product):
    if product["categoria"] != "Acessório":
        if "24-in" in product["descrição"].lower() or "24in" in product["descrição"].lower():
            # Dimensões mínimas (L x P x A): 1013 x 440 x 285 mm 
            return {
                "weight": 24.13
            }
        elif "36-in" in product["descrição"].lower() or "36in" in product["descrição"].lower():
            # Embalagem 1575 x 570 x 650 mm
            return {
                "weight": 71.00
            }
        elif "44in" in product["descrição"].lower() or "44in" in product["descrição"].lower() or "42-in" in product["descrição"].lower() or "42in" in product["descrição"].lower():
            # 2280 x 735 x 1200 mm
            return {
                "weight": 177.1
            }
        elif '64"' in product["descrição"].lower() or "64in" in product["descrição"].lower():
            #2800 x 750 x 1302 mm
            return {
                "weight": 262.1
            }
        else:
            return {
                "weight": 71.00
            }
    else:
        return {
            "weight": 3.00
        }
        
def extrair_familia(produto):
    # Remove prefixos como "HP" ou "Impressora HP"
    produto = re.sub(r"^(Impressora\s*)?HP\s+", "", produto, flags=re.IGNORECASE)

    # Pega só até o número ou aspas, removendo depois disso
    match = re.match(r"([A-Za-z ]+?[A-Za-z0-9\+\-]+)", produto)
    if match:
        return match.group(1).strip()
    return produto