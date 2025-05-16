import pandas as pd
import json
import requests
import os

API_KEY = 'AIzaSyChAV0iSmezL5Fe69P4gVYt-T6OsaY3Rck'
CX = '724fba8f8f1b84a1c'
CACHE_FILE = 'cache_plotter.json'

def carregar_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def buscar_imagem_hp(descricao):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": API_KEY,
        "cx": CX,
        "q": descricao,
        "searchType": "image",
        "num": 1,
        "siteSearch": "hp.com"
    }

    try:
        response = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code != 200:
            print(f"Erro {response.status_code} ao buscar imagem para: {descricao}")
            return None

        data = response.json()
        return data["items"][0]["link"]
    except Exception as e:
        print(f"Erro ao buscar imagem para: {descricao} - {e}")
        return None

def processar_plotter_data(arquivo_plotter):
    df_plotter = pd.read_excel(arquivo_plotter, engine='calamine', sheet_name='SP', header=5)
    df_limpo = df_plotter[df_plotter["PN"].notna()]
    lista_json = []
    cache = carregar_cache()

    for index, row in df_limpo.iterrows():
        pn = str(row["PN"]).strip()
        descricao = row["descrição"]
        preco = row["valor total com impostos"]

        if pn in cache:
            imagem_url = cache[pn]
        else:
            imagem_url = buscar_imagem_hp(descricao)
            if imagem_url:
                cache[pn] = imagem_url

        json_data = {
            "pn": pn,
            "descricao": descricao,
            "preco": preco,
            "imagem": imagem_url if imagem_url else ""
        }
        lista_json.append(json_data)

    salvar_cache(cache)

    with open("lista_plotter_json.json", "w", encoding="utf-8") as f:
        json.dump(lista_json, f, ensure_ascii=False, indent=2)

    print(f"Produtos processados: {len(lista_json)}")

