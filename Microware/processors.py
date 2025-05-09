import pandas as pd
import json
import requests
import re

def processar_microware_data(microware_data):
    products_df = pd.concat(microware_data.values(), ignore_index=True)

    combined_data = []
    for _, product in products_df.iterrows():
        try:
            # Tratamento do preço
            preco = product.get('Vr. de Venda Sugerido\n(Clientes sem IE em SP)', 0)
            if pd.isna(preco):
                preco = 0
            
            produto_data = {
                'name': str(product.get('Descrição', '')),
                'sku': str(product.get('PN', '')),
                'short_description': str(product.get('Descrição', '')),
                'description': str(product.get('Descrição', '')),
                'price': str(preco),
                'regular_price': str(preco),
                'stock_quantity': int(product.get('Saldo em Estoque', 0)), 
                'manage_stock': True,
                'attributes': processar_attributes(product),
                'dimmensions': processar_dimmensions(),
                'weight': tratar_peso(str(product.get('Peso', '0'))),
                'categories': process_categories(product),
            }
            combined_data.append(produto_data)
        except Exception as e:
            print(f"Erro ao processar produto: {str(e)}")
            continue

    return combined_data

def process_categories(product):
    categories = []
    with open('Microware/maps/categoriesWordpress.json', 'r') as f:
        categories_mapping = json.load(f)

    if product['Categoria'] == "Phone":
        categories.append({"id": 89})
    elif product['Categoria'] == "Bundle - Infraestrutura":
        categories.append({"id": 85})
    else:
        for category in categories_mapping:
            if category['name'].strip() == product['Categoria'].strip():
                categories.append({"id": category['id']})
                break

    return categories

def processar_attributes(product):
    attributes = []

    attributes.append({
        'id': 29,
        'options': str(product.get('Origem', '')),
        'visible': True
    })
   
    attributes.append({
        'id': 47,
        'options': str(product.get('Fabricante', '')),
        'visible': True
    }) 
    
    attributes.append({
        'id': 45,
        'options': str(product.get('Tipo de \nProduto', '')),
        'visible': True
    })

    attributes.append({
        'id': 15,
        'options': str(product.get('Condição', '')),
        'visible': True
    })

    attributes.append({
        'id': 46,
        'options': str(product.get('Dimensões da\n embalagem', '')),
        'visible': True
    })
    
    return attributes

def tratar_peso(peso: str) -> str:
    if not peso or not isinstance(peso, str):
        return "0"

    peso = peso.strip().lower().replace(",", ".")
    match = re.search(r"([\d.]+)\s*(kg|g)", peso)

    if not match:
        return "0"

    valor, unidade = match.groups()
    try:
        valor = float(valor)
    except ValueError:
        return "0"

    if unidade == "g":
        valor /= 1000

    return f"{valor:.3f}".rstrip("0").rstrip(".")

def processar_dimmensions():
    return {
                    "length": 2.1,
                    "width": 2.1,
                    "height": 2.1
                }