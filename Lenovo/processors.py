import pandas as pd
import json
import requests
import re

def processar_lenovo_data(lenovo_data):
    
    products_df = pd.concat(lenovo_data.values(), ignore_index=True)
    
    if "STATE" in products_df.columns:
        products_df = products_df[products_df["STATE"].str.lower().str.strip() == "sp"]
    
    if "CUSTOMER_TYPE" in products_df.columns:
        products_df = products_df[products_df["CUSTOMER_TYPE"].str.lower().str.strip() == "revenda sem regime"]
    
    MANUFACTURE = "Lenovo"
    STOCK = 10
    MARGIN = 20 

    images = buscar_imagens()
    normalized_values = normalize_values_list()

    combined_data = []
    code_and_dimmensions = []
    for _, product in products_df.iterrows():
        categories_data = processar_categories(product)
        
        product_name = product['PRODUCT_DESCRIPTION']
        if product_name.startswith('NB'):
            product_name = product_name.replace('NB', 'Notebook', 1)
       
        code_and_dimmensions.append({
            'code': product['PRODUCT_CODE'],
            'dimmensions': product['DIMENSION'],
            'weight': product['WEIGHT']
        })
        
        produto_data = {
            'name': product_name,
            'sku': product['PRODUCT_CODE'],
            'short_description': product['PH4_DESCRIPTION'],
            'description': product['PRODUCT_DESCRIPTION'],
            'regular_price': str(product['UNIT_GROSS_PRICE(R$)'] * (1 + MARGIN / 100)),
            'stock_quantity': 100,
            'attributes': processar_attributes(product),
            'meta_data': processar_fotos(product, images, normalized_values),
        }
        produto_data.update(categories_data)  # Adiciona as categorias no formato correto
        combined_data.append(produto_data)
    
    # Processa os dados da Anatel
    combined_data = processar_anatel(combined_data)
    combined_data = processr_deliveryinfo(combined_data, code_and_dimmensions)
    return combined_data

def processar_categories(product):

    CATEGORY_MAPPING = {
        "Notebook": ["Notebook"],
        "Desktop": ["Desktop"],
        "Workstation": ["Workstation"],
        "Tablet Android": ["Tablet"],
        "Visuals": ["Acessório"],
        "Smart Office": ["Equipamento para Reunião"]
    }
    
    # Obtém a lista de categorias ou usa ["Acessório"] como padrão
    category_names = CATEGORY_MAPPING.get(product['PH_BRAND'], ["Acessório"])


    categories = []
    with open('Lenovo/maps/categoriesWordpress.json', 'r') as f:
        categories_mapping = json.load(f)

    # Para cada nome de categoria mapeado
    for category_name in category_names:
        # Procura o ID correspondente no mapeamento
        for category in categories_mapping:
            if category['name'] == category_name:
                categories.append({"id": category['id']})
                break
    
    # Garante que sempre tenha pelo menos uma categoria
    if not categories:
        # Adiciona "Acessório" como categoria padrão
        for category in categories_mapping:
            if category['name'] == "Acessório":
                categories.append({"id": category['id']})
                break

    return {"categories": categories}

def processar_attributes(product):
    attributes = []
    with open('Lenovo/maps/attributesLenovo.json', 'r') as f:
        attributes_mapping = json.load(f)[0] 

    with open('Lenovo/maps/attributesWordpress.json', 'r') as f:
        attributes_mapping_wp = json.load(f)

    for lenovo_key, wp_name in attributes_mapping.items():
        # Encontra o ID correspondente no attributesWordpress
        wp_attribute = next((attr for attr in attributes_mapping_wp if attr['name'] == wp_name), None)

        if wp_attribute and lenovo_key in product:
            # Converte o valor para string e remove valores NaN
            valor = str(product[lenovo_key])
            if valor.lower() != 'nan' and valor.strip() != '':
                # Verifica se já existe um atributo com este ID
                atributo_existente = next((attr for attr in attributes if attr['id'] == wp_attribute['id']), None)
                
                if atributo_existente:
                    # Se o atributo já existe, adiciona o valor às opções
                    if valor not in atributo_existente['options']:
                        atributo_existente['options'].append(valor)
                else:
                    # Se o atributo não existe, cria um novo
                    attributes.append({
                        'id': wp_attribute['id'],
                        'options': [valor],
                        'visible': True
                    })
                    
    return attributes

def buscar_imagens():
    url = "https://eprodutos-integracao.microware.com.br/api/photos/allId"
    response = requests.get(url)
    if response.status_code != 200:
        return []
    # Converte a resposta JSON para DataFrame
    df = pd.DataFrame(response.json())
    return df

def processar_fotos(product, images, normalized_values):
    df = images
    base_url = "https://eprodutos-integracao.microware.com.br/api/photos/image/"

    normalize_family = normalized_values.get(product["PH4_DESCRIPTION"], "")


    # Tenta buscar imagens com a família específica
    filtered_df = df[
        (df['manufacturer'] == "Lenovo") & 
        (df['category'] == product['PH_BRAND']) & 
        (df['family'] == (normalize_family if normalize_family else product['PRODUCT_CODE']))
    ]

    # Se não encontrar, tenta com a família Default
    if filtered_df.empty:
        filtered_df = df[
            (df['manufacturer'] == "Lenovo") &
            (df['category'] == product['PH_BRAND']) &
            (df['family'] == "Default")
        ]

    # Se ainda estiver vazio, retorna meta_data vazio
    if filtered_df.empty:
        return []

    # Cria a lista de URLs das imagens
    image_urls = []
    for _, row in filtered_df.iterrows():
        if 'id' in row and 'extension' in row:
            image_url = f"{base_url}{row['id']}.{row['extension']}"
            image_urls.append(image_url)

    if not image_urls:
        return []

    # Primeira imagem é a principal (thumbnail), o resto é galeria
    meta_data = [
        {
            "key": "_external_image_url",
            "value": image_urls[0]
        }
    ]

    if len(image_urls) > 1:
        meta_data.append({
            "key": "_external_gallery_images",
            "value": image_urls[1:]  # restante vira galeria
        })

    return meta_data


def processar_anatel(data):
    try:

        df_anatel = pd.read_excel('panilhas/Anatel.xlsx', sheet_name='Lenovo')
        
        # Criar cache para famílias
        anatel_cache = {}
        for _, row in df_anatel.iterrows():
            family = str(row['Família Lenovo']).strip()
            if family.lower().startswith("lenovo "):
                family = family[3:]
            anatel_cache[family.lower()] = row['Código Anatel']
        
    

        produtos_com_anatel = 0
        for item in data:
            found_anatel = False
            
            # Primeira tentativa: buscar pelo Nome Produto
            family = item["short_description"].split(' ', 1)[1].lstrip() if ' ' in item["short_description"] else item["short_description"]
            family = family.strip()
            if family.lower().startswith("lenovo "):
                family = family[3:]
            
            # Buscar no cache (case insensitive)
            anatel_code = anatel_cache.get(family.lower())
            
            # Segunda tentativa: se não encontrou pelo Nome Produto, procurar pelo SKU
            if not anatel_code and "sku" in item:
                # Procurar no DataFrame original pelo SKU
                sku_str = str(item["sku"])
                sku_match = df_anatel[df_anatel['Família Lenovo'].astype(str).str.contains(sku_str, case=False, na=False)]
                if not sku_match.empty:
                    anatel_code = sku_match.iloc[0]['Código Anatel']
            
            if anatel_code:
                item["attributes"].append({"id": 13, "options": [str(anatel_code)]})
                found_anatel = True
                produtos_com_anatel += 1
        return data

    except Exception as e:
        print(f"\n=== Erro ao processar códigos Anatel ===")
        print(f"Erro: {str(e)}")
        return data

def processr_deliveryinfo(data, code_and_dimmensions):
        try:
            # Tentar carregar o primeiro arquivo, se falhar, tentar o segundo
            try:
                df_delivery = pd.read_excel('panilhas/DimensoesPeso.xlsx', sheet_name='Lenovo')
            except:
                try:
                    df_delivery = pd.read_excel('panilhas/DimensoesPeso.xlsx', sheet_name='Lenovo')
                except Exception as excel_error:
                    print(f"Erro ao ler arquivos de dimensões: {str(excel_error)}")
                    return data

            # Criar um dicionário para cache
            delivery_cache = {}
            
            # Pré-processar todas as linhas do DataFrame
            for _, row in df_delivery.iterrows():
                family = str(row['FAMÍLIA DE PRODUTOS']).strip()
                if family.lower().startswith("lenovo "):
                    family = family[3:]
                    
                dimensoes = str(row.get('DIMENSÕES COM EMBALAGEM (LxPxA)', ''))
                peso = row.get('PRESO COM EMBALAGEM kg', '')
                
                # Processar dimensões sem converter para metros
                dims_processed = {"largura": 0, "profundidade": 0, "altura": 0}
                if dimensoes and 'x' in dimensoes.lower():
                    dims = [d.strip() for d in dimensoes.lower().split('x')]
                    if len(dims) == 3:
                        try:
                            dims_processed = {
                                "largura": float(dims[0].replace(',', '.')),
                                "profundidade": float(dims[1].replace(',', '.')),
                                "altura": float(dims[2].replace(',', '.'))
                            }
                        except:
                            pass
                
                delivery_cache[family.lower()] = {
                    "dimensoes": dims_processed,
                    "peso": peso
                }

            # Processar os itens usando o cache e converter para metros
            for item in data:
                # Primeira tentativa: buscar pelo Nome Produto
                family = item["short_description"].split(' ', 1)[1].lstrip() if ' ' in item["short_description"] else item["short_description"]
                family = family.strip()
                if family.lower().startswith("lenovo "):
                    family = family[3:]
                
                # Buscar no cache (case insensitive)
                cached_info = delivery_cache.get(family.lower())
                
                # Segunda tentativa: se não encontrou pelo Nome Produto, procurar pelo SKU
                if not cached_info and "SKU" in item:
                    # Procurar no DataFrame original pelo SKU
                    sku_match = df_delivery[df_delivery['FAMÍLIA DE PRODUTOS'].str.contains(item["sku"], case=False, na=False)]
                    if not sku_match.empty:
                        row = sku_match.iloc[0]
                        dimensoes = str(row.get('DIMENSÕES COM EMBALAGEM (LxPxA)', ''))
                        peso = row.get('PRESO COM EMBALAGEM kg', '')
                        
                        dims_processed = {"largura": 0, "profundidade": 0, "altura": 0}
                        if dimensoes and 'x' in dimensoes.lower():
                            dims = [d.strip() for d in dimensoes.lower().split('x')]
                            if len(dims) == 3:
                                try:
                                    dims_processed = {
                                        "largura": float(dims[0].replace(',', '.')),
                                        "profundidade": float(dims[1].replace(',', '.')),
                                        "altura": float(dims[2].replace(',', '.'))
                                    }
                                except:
                                    pass
                        
                        cached_info = {
                            "dimensoes": dims_processed,
                            "peso": peso
                        }

                # Terceira tentativa: usar o nome completo do produto
                if not cached_info and "name" in item:
                    
                    for code in code_and_dimmensions:
                        if code["code"] == item["sku"]:
                            cached_info = {
                                "dimensoes": extrair_dimensoes(code["dimmensions"]),
                                "peso": extrair_peso(code["weight"])
                            }
               
                if cached_info:

                    dimensions = {
                        "length": cached_info["dimensoes"]["profundidade"] / 100.0,
                        "width": cached_info["dimensoes"]["largura"] / 100.0,
                        "height": cached_info["dimensoes"]["altura"] / 100.0
                    }
                    item["dimensions"] = dimensions
                    item["weight"] = cached_info["peso"]

            return data

        except Exception as e:
            print(f"Erro ao processar informações de entrega: {str(e)}")
            return data


def extrair_dimensoes(dimensoes_str):
    # Procura por padrão de dimensões no formato "X x Y x Z"
    padrao = r'(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)'
    match = re.search(padrao, dimensoes_str)
    if match:
        return {
            "largura": float(match.group(1)),
            "profundidade": float(match.group(2)),
            "altura": float(match.group(3))
        }
    return {"largura": 0, "profundidade": 0, "altura": 0}

def extrair_peso(peso_str):
    # Procura por qualquer número seguido de Kg ou KG
    padrao = r'(\d+(?:\.\d+)?)\s*[kK][gG]'
    match = re.search(padrao, peso_str)
    if match:
        peso = float(match.group(1))
        # Se o peso for 0.0, retorna 0
        if peso == 0.0:
            return 0
        return peso
    return 0

def normalize_values_list():
    normalize_values_list = []
    request = requests.get(f"https://eprodutos-integracao.microware.com.br/api/normalize-values")
    if request.status_code == 200:
        response_data = request.json()
        # Encontra o item que contém os dados da família
        for item in response_data:
            if item["column"] == "Familia":
                normalize_values_list = item["from_to"]
                break
    return normalize_values_list