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
    
    print("Total de produtos encontrados:", len(todos_produtos))
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
     
    return combined_data

def enviar_produtos(combined_data):
    token_data = get_token()
    access_token = token_data["access_token"]
    id_loja = "6451"
    print("Login realizado com sucesso: ", access_token)
    results = []
    for product in combined_data:
        
        response = requests.post(
            f"https://rest.hub2b.com.br/catalog/product/setsku/{id_loja}?access_token={access_token}",
            json=product
        )
        results.append(response.json())
    return results