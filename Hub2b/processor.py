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

def _get_utils_path():
    # Obtém o diretório atual do arquivo processor.py
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Sobe um nível e entra na pasta Utils
    return os.path.join(os.path.dirname(current_dir), 'Utils')

def _normalizar_texto(texto):
    if not texto:
        return ""
    # Remove acentos
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
    # Converte para minúsculo
    return texto.lower().strip()

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


        product_data = {
            "sku": product["sku"], 
            "parentSku": product["sku"], 
            "ean13": next((attr["options"][0] for attr in product["attributes"] if attr["slug"] == "pa_codigo-ean"), None),
            "warrantyMonths": 12, 
            "handlingTime": lead_time, 
            "stock": 10, 
            "weightKg": extrair_peso(product.get("weight")) if product.get("weight") else "0",
            "url": product["permalink"],
            "categoryCode": next((cat["name"] for cat in product["categories"]), ""),
            "name": limpar_texto(product["name"]), 
            "sourceDescription": limpar_texto(product["description"]) or limpar_texto(product.get("short_description", "")), 
            "description": limpar_texto(product["description"]) or limpar_texto(product.get("short_description", "")), 
            "brand": marca,
            "ncm": get_ncm(product), 
            "height_m": str(float(product["dimensions"]["height"])/100) if product["dimensions"].get("height") else "0",
            "width_m": str(float(product["dimensions"]["width"])/100) if product["dimensions"].get("width") else "0",
            "length_m": str(float(product["dimensions"]["length"])/100) if product["dimensions"].get("length") else "0",
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
        id_loja = "2792"
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

        # Função auxiliar para formatar EAN13
        def formatar_ean13(ean):
            if not ean:
                return None
            # Remove caracteres não numéricos e converte para string
            ean = ''.join(filter(str.isdigit, str(ean)))
            # Garante que tenha 13 dígitos, preenchendo com zeros à esquerda se necessário
            return ean.zfill(13) if len(ean) <= 13 else ean

        # Obtém o EAN13 e formata
        ean13 = next((attr["options"][0] for attr in product["attributes"] if attr["slug"] == "pa_codigo-ean"), None)
        if not ean13:
            ean13 = get_delivery_info(product, "ean13", product["categories"][0]["name"])
        ean13_formatado = formatar_ean13(ean13)

        # Dicionário base com os campos fixos
        produto_dict = {
            "Nome Produto": limpar_texto(product["name"]),
            "Descrição": limpar_texto(product["description"]),
            "Descrição Personalizada": limpar_texto(product["description"]),
            "URL do produto": product["permalink"],
            "SKU": product["sku"],
            "EAN ou ISBN (13 digitos)": ean13_formatado,
            "Marca": MANUFACTURE,
            "Preço De": product["price"],
            "Preço Por": product["price"],
            "Tempo Compra / Fabricação": lead_time,
            "Estoque": 10,
            "Categoria": product["categories"][0]["name"] if product.get("categories") else "",
            "Altura*(m)": str(float(product["dimensions"]["height"])/100) if product["dimensions"].get("height") else get_delivery_info(product, "height_m", product["categories"][0]["name"]),
            "Largura*(m)": str(float(product["dimensions"]["width"])/100) if product["dimensions"].get("width") else get_delivery_info(product, "width_m", product["categories"][0]["name"]),
            "Profundidade*(m)": str(float(product["dimensions"]["length"])/100) if product["dimensions"].get("length") else get_delivery_info(product, "length_m", product["categories"][0]["name"]),
            "Peso*(kg)": get_delivery_info(product, "weightKg", product["categories"][0]["name"]),
            "Url Imagem 1": next((meta["value"] for meta in product["meta_data"] if meta["key"] == "_external_image_url"), "")
        }


        # Adiciona os atributos dinamicamente
        if product.get("attributes"):
            idx = 1
            for attr in product["attributes"]:
                # Ignora o atributo EAN pois já temos como coluna fixa
                if attr["slug"] == "pa_codigo-ean":
                    continue
                    
                produto_dict[f"Atributo {idx}"] = attr["name"]
                # Junta todos os valores do atributo em uma única string, separados por vírgula
                produto_dict[f"Valores {idx}"] = ", ".join(attr["options"]) if attr["options"] else ""
                idx += 1

        combined_data.append(produto_dict)
    return combined_data

def extrair_peso(weight):
    if isinstance(weight, dict):
        return str(weight.get("weight", "0"))
    return str(weight)
  
def _carregar_delivery_info():
    with open('Utils/delivery_info.json', 'r') as f:
        return json.load(f)

# Pegar infos delivery na pasta Utils 
def get_delivery_info(product, value, category):
    delivery_info = _carregar_delivery_info()
    info = delivery_info.get(category)
    if (category != "Plotter"):
        if value == "weightKg":
            return info.get("weightKg")
        elif value == "height_m":
            return info.get("height_m")
        elif value == "width_m":
            return info.get("width_m")
        elif value == "length_m":
            return info.get("length_m")
        return "0" 
    else:
 
        #Ler xlsx que está na pasta Hub2b/delivery_info
        df = pd.read_excel('Hub2b/Especificacoes Tecnicas Impressoras 1.xlsx')
        #relacionar product via sku com o df
        df_sku = df[df['SKU'] == product["sku"]]
        if df_sku.empty:
            if value == "weightKg":
                return extrair_peso(product.get("weight")) if product.get("weight") else "0"
                
            else:
                return "0"
        else:
            if value == "ean13":
                return df_sku["EAN"].values[0]
            if value == "weightKg":
                return df_sku["Peso da embalagem (kg)"].values[0]
            elif value == "height_m":
                return df_sku["Altura da embalagem (cm)"].values[0] / 100
            elif value == "width_m":
                return df_sku["Largura da embalagem (cm)"].values[0] / 100
            elif value == "length_m":
                return df_sku["Comprimento da embalagem (cm)"].values[0] / 100
        

def _carregar_ncm_cache():
    global _ncm_cache
    if _ncm_cache is None:
        utils_path = _get_utils_path()
        with open(os.path.join(utils_path, 'ncm.json'), 'r') as f:
            _ncm_cache = json.load(f)
    return _ncm_cache

def _carregar_categoria_map():
    global _categoria_map_cache
    if _categoria_map_cache is None:
        utils_path = _get_utils_path()
        with open(os.path.join(utils_path, 'categoria_map.json'), 'r') as f:
            _categoria_map_cache = json.load(f)
    return _categoria_map_cache

        