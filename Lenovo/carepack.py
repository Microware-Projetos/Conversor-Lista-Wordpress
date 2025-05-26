import pandas as pd
import json

def processar_carepack_data(arquivo):
    try:
        # # Lê o arquivo Excel
        df = pd.read_excel(arquivo, engine='calamine', sheet_name='Q1', header=5)
        
        print(df.columns)

        # Lista para armazenar os produtos processados
        produtos = []
        
        # Processa cada linha do DataFrame
        for _, row in df.iterrows():
            # Aqui você precisará ajustar os nomes das colunas de acordo com seu arquivo Excel
            produto_data = {
                'name': row['Descrição do Serviço'],
                'sku': row['PN'],
                'short_description': row['Descrição do Serviço'],
                'description': row['Descrição do Serviço'],
                'price': row['Preço Bruto'] / (1 - (20 / 100)) if row['Preço Bruto'] is not None else None,
                'regular_price': row['Preço Bruto'] / (1 - (20 / 100)) if row['Preço Bruto'] is not None else None,
                'stock_quantity': 10,
                'attributes': processar_attributes(row),
                'meta_data': processar_fotos(),
                'dimmensions': processar_dimmensions(),
                'weight': processar_weight(),
                'categories': processar_categories(),
                "manage_stock": True,
            }
            
            # Adiciona o produto à lista
            produtos.append(produto_data)
            
        # Salva o JSON com os produtos
        with open('produtos_carepack.json', 'w') as f:
            json.dump(produtos, f, ensure_ascii=False, indent=4)
            
        return produtos  # Retorna a lista de produtos
        
    except Exception as e:
        print(f"Erro ao processar arquivo Care Pack: {str(e)}")
        raise Exception(f"Erro ao processar arquivo Care Pack: {str(e)}")

def processar_categories():
    categories = []
    with open('Lenovo/maps/categoriesWordpress.json', 'r') as f:
        categories_mapping = json.load(f)
    
    for category in categories_mapping:
        if category['name'] == "Serviço":
            categories.append({"id": category['id']})
            break
    return categories

def processar_attributes(product):
    attributes = []

    attributes.append({
        'id': 550,
        'options': [product['Tipo de Serviço']],
        'visible': True
    })

    attributes.append({
        'id': 14,
        'options': [product['Compatibilidade']],
        'visible': True
    })

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
        "value": "https://eprodutos-integracao.microware.com.br/api/photos/image/67c1e66abe14dc12f6b266e2.png"
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

