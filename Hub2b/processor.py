import pandas as pd
import json
import asyncio
import aiohttp
import time
import requests
import re
from .auth import get_token

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
    elif marca == 'HP':
        url_base = "https://ecommerce.microware.com.br/hp/wp-json/wc/v3/products"
    
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
                    
                todos_produtos.extend(produtos)
                page += 1

    # Salvar Json
    with open('produtos_woocommerce_processados.json', 'w') as f:
        json.dump(todos_produtos, f, indent=4)
    return todos_produtos

def processar_produtos(produtos, marca):
    combined_data = []
   
    for product in produtos:
        product_data = {
            "sku": product["sku"], 
            "parentSku": product["sku"], 
            "ean13": next((attr["options"][0] for attr in product["attributes"] if attr["slug"] == "pa_codigo-ean"), None),
            "warrantyMonths": 30, 
            "handlingTime": 30, 
            "stock": product["stock_quantity"], 
            "weightKg": product["weight"], 
            "url": product["permalink"], 
            "name": limpar_texto(product["name"]), 
            "sourceDescription": limpar_texto(product["description"]), 
            "description": limpar_texto(product["description"]), 
            "brand": marca, 
            "ncm": "", 
            "height_m": product["dimensions"]["height"] if product["dimensions"]["height"] else "0",
            "width_m": product["dimensions"]["width"] if product["dimensions"]["width"] else "0",
            "length_m": product["dimensions"]["length"] if product["dimensions"]["length"] else "0",
            "priceBase": product["regular_price"],
            "priceSale": product["price"],
            "images": [
                {"url": meta["value"]} for meta in product["meta_data"] 
                if meta["key"] == "_external_image_url"
            ] + [
                {"url": url} for meta in product["meta_data"] 
                if meta["key"] == "_external_gallery_images" 
                for url in meta["value"]
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
        
        # Semáforo para limitar requisições concorrentes
        sem = asyncio.Semaphore(5)
        results = []
        produtos_enviados = 0
        produtos_com_erro = 0
        historico_envios = []
        
        # Dividir os produtos em lotes de 5
        lotes = [combined_data[i:i + 5] for i in range(0, len(combined_data), 5)]
        
        async def enviar_lote(lote, tentativa=1):
            nonlocal produtos_enviados, produtos_com_erro
            async with sem:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            f"https://rest.hub2b.com.br/catalog/product/setsku/{id_loja}?access_token={access_token}",
                            json=lote
                        ) as response:
                            result = await response.json()
                            if response.status != 200:
                                erro_msg = result.get('message', 'Erro desconhecido')
                                skus = [produto.get('sku', 'N/A') for produto in lote]
                                print(f"\nErro ao enviar lote (Tentativa {tentativa}): Status {response.status}")
                                print(f"SKUs afetados: {', '.join(skus)}")
                                print(f"Detalhes do erro: {erro_msg}")
                                
                                # Registra no histórico
                                for produto in lote:
                                    historico_envios.append({
                                        "sku": produto.get("sku"),
                                        "status": "erro",
                                        "tentativa": tentativa,
                                        "erro": erro_msg
                                    })
                                
                                produtos_com_erro += len(lote)
                                return {"status": "erro", "lote": lote, "erro": erro_msg}
                            else:
                                produtos_enviados += len(lote)
                                # Registra no histórico
                                for produto in lote:
                                    historico_envios.append({
                                        "sku": produto.get("sku"),
                                        "status": "sucesso",
                                        "tentativa": tentativa
                                    })
                                print(f"\rProgresso: {produtos_enviados}/{len(combined_data)} produtos enviados | Erros: {produtos_com_erro}", end="")
                                await asyncio.sleep(0.2)
                                return {"status": "sucesso", "lote": lote}
                except Exception as e:
                    produtos_com_erro += len(lote)
                    skus = [produto.get('sku', 'N/A') for produto in lote]
                    # Registra no histórico
                    for produto in lote:
                        historico_envios.append({
                            "sku": produto.get("sku"),
                            "status": "erro",
                            "tentativa": tentativa,
                            "erro": str(e)
                        })
                    print(f"\nErro ao enviar lote (Tentativa {tentativa}): {str(e)}")
                    print(f"SKUs afetados: {', '.join(skus)}")
                    return {"status": "erro", "lote": lote, "erro": str(e)}
        
        # Cria tarefas para todos os lotes
        tasks = [enviar_lote(lote) for lote in lotes]
        
        # Executa todas as tarefas e aguarda os resultados
        results = await asyncio.gather(*tasks)
        
        # Processa os lotes com erro para retry
        lotes_com_erro = [result["lote"] for result in results if result["status"] == "erro"]
        
        # Realiza até 3 tentativas para os lotes com erro
        for tentativa in range(2, 4):  # Começa em 2 pois a primeira tentativa já foi feita
            if not lotes_com_erro:
                break
                
            print(f"\n\nIniciando tentativa {tentativa} para {len(lotes_com_erro)} lotes com erro...")
            retry_tasks = [enviar_lote(lote, tentativa) for lote in lotes_com_erro]
            retry_results = await asyncio.gather(*retry_tasks)
            
            # Atualiza a lista de lotes com erro
            lotes_com_erro = [result["lote"] for result in retry_results if result["status"] == "erro"]
        
        # Salva o histórico em um arquivo JSON
        with open('historico_envios.json', 'w') as f:
            json.dump(historico_envios, f, indent=4)
        
        print(f"\n\nProcesso finalizado!")
        print(f"Total de produtos: {len(combined_data)}")
        print(f"Produtos enviados com sucesso: {produtos_enviados}")
        print(f"Produtos com erro: {produtos_com_erro}")
        print(f"Histórico de envios salvo em 'historico_envios.json'")
        
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
