import pandas as pd
import json

def processar_carepack_data(arquivo):
    try:
        # Lê o arquivo Excel
        df = pd.read_excel(arquivo, engine='calamine', sheet_name='Channel', header=2)

        # Lista para armazenar os produtos processados
        produtos = []
        
        # Processa cada linha do DataFrame
        for _, row in df.iterrows():
            # Aqui você precisará ajustar os nomes das colunas de acordo com seu arquivo Excel
            produto_data = {
                'name': row['Description'],
                'sku': row['PN'],
                'short_description': row['Description'],
                'description': row['Description'],
                'price': row['Canal - Custo \r\ncom impostos'] / (1 - (20 / 100)) if row['Canal - Custo \r\ncom impostos'] is not None else None,
                'regular_price': row['Canal - Custo \r\ncom impostos'] / (1 - (20 / 100)) if row['Canal - Custo \r\ncom impostos'] is not None else None,
                'stock_quantity': 10,
                'attributes': processar_attributes(),
                'meta_data': processar_fotos(),
                'dimmensions': processar_dimmensions(),
                'weight': processar_weight(),
                'categories': processar_categories(),
                "manage_stock": True,
            }
            
            # Adiciona o produto à lista
            produtos.append(produto_data)
            
            #gerar json com os produtos
            with open('produtos_carepack.json', 'w') as f:
                json.dump(produtos, f)
        return produtos
        
    except Exception as e:
        print(f"Erro ao processar arquivo Care Pack: {str(e)}")
        raise Exception(f"Erro ao processar arquivo Care Pack: {str(e)}") 

def processar_categories():
    categories = []
    with open('HP/maps/categoriesWordpress.json', 'r') as f:
        categories_mapping = json.load(f)
    
    for category in categories_mapping:
        if category['name'] == "Serviço":
            categories.append({"id": category['id']})
            break
    return categories

def processar_attributes():
    attributes = []
    attributes.append({
        'id': 9,
        'options': ["Serviço"],
        'visible': True
    })
    return attributes

def processar_fotos():

    meta_data = [
    {
        "key": "_external_image_url",
        "value": "https://eprodutos-integracao.microware.com.br/api/photos/image/682c799e253b92080f3ebda5.jpeg"
    }]
    return meta_data

def processar_dimmensions():
    return {
            "length": 0,
            "width": 0,
            "height": 0
        }

def processar_weight():
    return {
        "weight": 0
    }

