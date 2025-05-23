import pandas as pd
import json
import asyncio
import aiohttp
import time
import requests
import re
import unicodedata
import os
from .auth import get_token

# Cache para os arquivos
_ncm_cache = None
_categoria_map_cache = None
_delivery_info_cache = None

def _get_utils_path():
    # Obtém o diretório atual do arquivo processor.py
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Sobe um nível e entra na pasta Utils
    return os.path.join(os.path.dirname(current_dir), 'Utils')

def _carregar_categoria_map():
    global _categoria_map_cache
    if _categoria_map_cache is None:
        try:
            utils_path = _get_utils_path()
            categoria_map_path = os.path.join(utils_path, 'categoria_map.json')
            with open(categoria_map_path, 'r', encoding='utf-8') as f:
                _categoria_map_cache = json.load(f)
        except Exception as e:
            print(f"Erro ao carregar arquivo de mapeamento de categorias: {str(e)}")
            _categoria_map_cache = {}
    return _categoria_map_cache

def _carregar_delivery_info():
    global _delivery_info_cache
    if _delivery_info_cache is None:
        try:
            utils_path = _get_utils_path()
            delivery_info_path = os.path.join(utils_path, 'delivery_info.json')
            with open(delivery_info_path, 'r', encoding='utf-8') as f:
                _delivery_info_cache = json.load(f)
        except Exception as e:
            print(f"Erro ao carregar arquivo de informações de entrega: {str(e)}")
            _delivery_info_cache = {}
    return _delivery_info_cache

def _get_delivery_info(categoria_nome):
    delivery_info = _carregar_delivery_info()
    return delivery_info.get(categoria_nome, {
        "weightKg": "0",
        "height_m": "0",
        "width_m": "0",
        "length_m": "0"
    })

def _normalizar_texto(texto):
    if not texto:
        return ""
    # Remove acentos
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
    # Converte para minúsculo
    return texto.lower().strip()

def _carregar_ncm_cache():
    global _ncm_cache
    if _ncm_cache is None:
        try:
            utils_path = _get_utils_path()
            ncm_path = os.path.join(utils_path, 'ncm.json')
            with open(ncm_path, 'r', encoding='utf-8') as f:
                _ncm_cache = json.load(f)
        except Exception as e:
            print(f"Erro ao carregar arquivo NCM: {str(e)}")
            _ncm_cache = {}
    return _ncm_cache

def limpar_texto(texto):
    if not texto:
        return ""
    # Remove tags HTML
    texto = re.sub(r'<[^>]+>', '', texto)
    # Remove quebras de linha e espaços extras
    texto = re.sub(r'\n+', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()

async def buscar_produtos(marca, consumer_key, consumer_secret):
    url_base = None
    todos_produtos = []
    
    if marca == 'Lenovo':
        url_base = "https://ecommerce.microware.com.br/lenovo/wp-json/wc/v3/products"
        categoria_ignorar = 33
    elif marca == 'HP':
        url_base = "https://ecommerce.microware.com.br/hp/wp-json/wc/v3/products"
        categoria_ignorar = 32
    
    async with aiohttp.ClientSession() as session:
        page = 1
        while True:
            async with session.get(
                url_base,
                auth=aiohttp.BasicAuth(consumer_key, consumer_secret),
                params={"per_page": 100, "page": page}
            ) as response:
                produtos = await response.json()
                
                if not produtos:
                    break
                
                # Filtra os produtos que não pertencem à categoria que deve ser ignorada
                produtos_filtrados = [
                    produto for produto in produtos 
                    if not any(cat['id'] == categoria_ignorar for cat in produto.get('categories', []))
                ]
                    
                todos_produtos.extend(produtos_filtrados)
                page += 1

    # Salvar Json
    with open('produtos_woocommerce_processados.json', 'w') as f:
        json.dump(todos_produtos, f, indent=4)
    return todos_produtos

def processar_produtos(produtos, marca):
    combined_data = []
   
    for product in produtos:
       
        if product.get("shipping_class") == "importado" or product.get("shipping_class") == "Importado":
            lead_time = 60
        else:
            lead_time = 45

        # Obtém a categoria do produto para usar como fallback
        categoria_nome = None
        if product.get("categories") and len(product["categories"]) > 0:
            categoria_slug = product["categories"][0].get("slug")
            if categoria_slug:
                categoria_map = _carregar_categoria_map()
                categoria_nome = categoria_map.get(categoria_slug)

        # Obtém informações de entrega da categoria
        delivery_info = _get_delivery_info(categoria_nome) if categoria_nome else None

        product_data = {
            "sku": product["sku"], 
            "parentSku": product["sku"], 
            "ean13": next((attr["options"][0] for attr in product["attributes"] if attr["slug"] == "pa_codigo-ean"), None),
            "warrantyMonths": 12, 
            "handlingTime": lead_time, 
            "stock": 10, 
            "weightKg": str(product["weight"]) if product.get("weight") else delivery_info["weightKg"] if delivery_info else "0",
            "url": product["permalink"],
            "categoryCode": next((cat["name"] for cat in product["categories"]), ""),
            "name": limpar_texto(product["name"]), 
            "sourceDescription": limpar_texto(product["description"]) or limpar_texto(product.get("short_description", "")), 
            "description": limpar_texto(product["description"]) or limpar_texto(product.get("short_description", "")), 
            "brand": marca,
            "ncm": get_ncm(product), 
            "height_m": str(float(product["dimensions"]["height"])/100) if product["dimensions"].get("height") else delivery_info["height_m"] if delivery_info else "0",
            "width_m": str(float(product["dimensions"]["width"])/100) if product["dimensions"].get("width") else delivery_info["width_m"] if delivery_info else "0",
            "length_m": str(float(product["dimensions"]["length"])/100) if product["dimensions"].get("length") else delivery_info["length_m"] if delivery_info else "0",
            "priceBase": product["regular_price"],
            "priceSale": product["price"],
            "images": [
                {"url": url, "rank": idx + 1} 
                for idx, url in enumerate([
                    meta["value"] for meta in product["meta_data"] 
                    if meta["key"] == "_external_image_url"
                ] + [
                    url for meta in product["meta_data"] 
                    if meta["key"] == "_external_gallery_images" 
                    for url in meta["value"]
                ])
            ],
            "specifications": [
                {
                    "name": limpar_texto(attr["name"]),
                    "value": limpar_texto(attr["options"][0]) if attr["options"] else "",
                    "type": 0
                } for attr in product["attributes"] 
                if attr["slug"] != "pa_codigo-ean"
            ]
        }
        combined_data.append(product_data)
        # criar json de produtos processados
        with open('produtos_hub2b_processados.json', 'w') as f:
            json.dump(combined_data, f, indent=4)
            
    return combined_data

async def enviar_produtos(combined_data):
    try:
        token_data = get_token()
        access_token = token_data["access_token"]
        id_loja = "6451"
        print("Login realizado com sucesso: ", access_token)
        print(f"\nIniciando envio de {len(combined_data)} produtos...")
        
        # Semáforo para limitar a 3 requisições simultâneas
        sem = asyncio.Semaphore(3)
        # Controle de taxa para garantir 3 requisições por segundo
        rate_limiter = asyncio.Semaphore(3)
        results = []
        produtos_enviados = 0
        produtos_com_erro = 0
        historico_envios = []
        
        async def reset_rate_limiter():
            while True:
                await asyncio.sleep(1)  # Espera 1 segundo
                for _ in range(3):  # Libera 3 slots
                    try:
                        rate_limiter.release()
                    except ValueError:
                        pass  # Ignora se o semáforo já estiver no máximo
        
        # Inicia o reset do rate limiter em background
        asyncio.create_task(reset_rate_limiter())
        
        async def enviar_produto(produto, tentativa=1):
            nonlocal produtos_enviados, produtos_com_erro
            async with sem:  # Limita a 3 requisições simultâneas
                async with rate_limiter:  # Garante 3 requisições por segundo
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.post(
                                f"https://rest.hub2b.com.br/catalog/product/setsku/{id_loja}?access_token={access_token}",
                                json=[produto]  # Envia um produto por vez
                            ) as response:
                                result = await response.json()
                                if response.status != 200:
                                    erro_msg = result.get('message', 'Erro desconhecido')
                                    print(f"\nErro ao enviar produto (Tentativa {tentativa}): Status {response.status}")
                                    print(f"SKU afetado: {produto.get('sku', 'N/A')}")
                                    print(f"Detalhes do erro: {erro_msg}")
                                    
                                    historico_envios.append({
                                        "sku": produto.get("sku"),
                                        "status": "erro",
                                        "tentativa": tentativa,
                                        "erro": erro_msg
                                    })
                                    
                                    produtos_com_erro += 1
                                    return {"status": "erro", "produto": produto, "erro": erro_msg}
                                else:
                                    produtos_enviados += 1
                                    historico_envios.append({
                                        "sku": produto.get("sku"),
                                        "status": "sucesso",
                                        "tentativa": tentativa
                                    })
                                    print(f"\rProgresso: {produtos_enviados}/{len(combined_data)} produtos enviados | Erros: {produtos_com_erro}", end="")
                                    return {"status": "sucesso", "produto": produto}
                    except Exception as e:
                        produtos_com_erro += 1
                        historico_envios.append({
                            "sku": produto.get("sku"),
                            "status": "erro",
                            "tentativa": tentativa,
                            "erro": str(e)
                        })
                        print(f"\nErro ao enviar produto (Tentativa {tentativa}): {str(e)}")
                        print(f"SKU afetado: {produto.get('sku', 'N/A')}")
                        return {"status": "erro", "produto": produto, "erro": str(e)}
        
        # Cria tarefas para todos os produtos
        tasks = [enviar_produto(produto) for produto in combined_data]
        
        # Executa todas as tarefas e aguarda os resultados
        results = await asyncio.gather(*tasks)
        
        # Processa os produtos com erro para retry
        produtos_com_erro = [result["produto"] for result in results if result["status"] == "erro"]
        
        # Realiza até 3 tentativas para os produtos com erro
        for tentativa in range(2, 4):  # Começa em 2 pois a primeira tentativa já foi feita
            if not produtos_com_erro:
                break
                
            print(f"\n\nIniciando tentativa {tentativa} para {len(produtos_com_erro)} produtos com erro...")
            retry_tasks = [enviar_produto(produto, tentativa) for produto in produtos_com_erro]
            retry_results = await asyncio.gather(*retry_tasks)
            
            # Atualiza a lista de produtos com erro
            produtos_com_erro = [result["produto"] for result in retry_results if result["status"] == "erro"]
        
        print(f"\n\nProcesso finalizado!")
        print(f"Total de produtos: {len(combined_data)}")
        print(f"Produtos enviados com sucesso: {produtos_enviados}")
        print(f"Produtos com erro: {produtos_com_erro}")
        print(f"Histórico de envios salvo em 'historico_envios.json'")
        
        # Salva o histórico em arquivo
        with open('historico_envios.json', 'w') as f:
            json.dump(historico_envios, f, indent=4)
        
        return {
            "total": len(combined_data),
            "enviados": produtos_enviados,
            "erros": produtos_com_erro,
            "results": results,
            "historico": historico_envios
        }
    except Exception as e:
        print(f"Erro geral no processo de envio: {str(e)}")
        import traceback
        print(f"Traceback completo: {traceback.format_exc()}")
        raise

def get_ncm(product):
    if not product:
        return ""
        
    # Primeiro tenta pegar o NCM direto do produto
    ncm = product.get("ncm")
    if ncm and str(ncm).strip():
        return str(ncm).strip()
    
    # Se não tiver NCM direto, busca pela categoria
    try:
        ncm_categorias = _carregar_ncm_cache()
        categoria_map = _carregar_categoria_map()
        
        # Tenta encontrar a categoria do produto
        if product.get("categories"):
            for categoria in product["categories"]:
                # Tenta primeiro pelo slug
                if categoria.get("slug"):
                    nome_categoria = categoria_map.get(categoria["slug"])
                    if nome_categoria and nome_categoria in ncm_categorias:
                        return str(ncm_categorias[nome_categoria])
                
                # Se não encontrou pelo slug, tenta pelo nome
                if categoria.get("name"):
                    nome_categoria = categoria["name"]
                    if nome_categoria in ncm_categorias:
                        return str(ncm_categorias[nome_categoria])
                    
        # Se não encontrou pela categoria, tenta pelo shipping_class
        shipping_class = product.get("shipping_class", "").lower()
        if shipping_class:
            for nome_cat, ncm_valor in ncm_categorias.items():
                if _normalizar_texto(nome_cat) == shipping_class:
                    return str(ncm_valor)
                    
    except Exception as e:
        print(f"Erro ao buscar NCM para produto {product.get('sku', 'N/A')}: {str(e)}")
    
    return ""

#gerar panilha hub2b
def gerar_panilha_hub2b(products, MANUFACTURE):
    combined_data = []
    for product in products:
        
        lead_time = 0
        if product.get("shipping_class") == "importado" or product.get("shipping_class") == "Importado":
            lead_time = 60
        else:
            lead_time = 45

        categoria_nome = None
        if product.get("categories") and len(product["categories"]) > 0:
            categoria_slug = product["categories"][0].get("slug")
            if categoria_slug:
                categoria_map = _carregar_categoria_map()
                categoria_nome = categoria_map.get(categoria_slug)

        # Obtém informações de entrega da categoria
        delivery_info = _get_delivery_info(categoria_nome) if categoria_nome else None

        # Dicionário base com os campos fixos
        produto_dict = {
            "Nome Produto": limpar_texto(product["name"]),
            "Descrição": limpar_texto(product["description"]),
            "Descrição Personalizada": limpar_texto(product["description"]),
            "URL do produto": product["permalink"],
            "SKU": product["sku"],
            "EAN ou ISBN (13 digitos)": "",
            "Marca": MANUFACTURE,
            "Preço De": product["price"],
            "Preço Por": product["price"],
            "Tempo Compra / Fabricação": lead_time,
            "Estoque": 10,
            "Categoria": product["categories"][0]["name"] if product.get("categories") else "",
            "Altura*(m)": str(float(product["dimensions"]["height"])/100) if product["dimensions"].get("height") else delivery_info["height_m"] if delivery_info else "0",
            "Largura*(m)": str(float(product["dimensions"]["width"])/100) if product["dimensions"].get("width") else delivery_info["width_m"] if delivery_info else "0",
            "Profundidade*(m)": str(float(product["dimensions"]["length"])/100) if product["dimensions"].get("length") else delivery_info["length_m"] if delivery_info else "0",
            "Peso*(kg)": extrair_peso(product.get("weight")) if product.get("weight") else delivery_info["weightKg"] if delivery_info else "0",
            "Url Imagem 1": next((meta["value"] for meta in product["meta_data"] if meta["key"] == "_external_image_url"), "")
        }

        # Adiciona os atributos dinamicamente
        if product.get("attributes"):
            for idx, attr in enumerate(product["attributes"], start=1):
                produto_dict[f"Atributo {idx}"] = attr["name"]
                # Junta todos os valores do atributo em uma única string, separados por vírgula
                produto_dict[f"Valores {idx}"] = ", ".join(attr["options"]) if attr["options"] else ""

        combined_data.append(produto_dict)
    return combined_data

def extrair_peso(weight):
    if isinstance(weight, dict):
        return str(weight.get("weight", "0"))
    return str(weight)
  
    
