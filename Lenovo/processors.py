import pandas as pd
import json
import requests
import re
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

EmailProducts = []
normalized_values_cache = {}
product_cache = {}  # Cache para produtos por SKU
CACHE_FILE = 'Lenovo/cache/product_cache.json'

# Mapeamento de categorias para fotos padrão
DEFAULT_PHOTOS = {
    17: "https://eprodutos-integracao.microware.com.br/api/photos/image/67f027b0ff6d81181139ddfe.png",  # Acessório
    18: "https://eprodutos-integracao.microware.com.br/api/photos/image/67c1e5d5be14dc12f6b266dc.png",  # Desktop
    19: "https://eprodutos-integracao.microware.com.br/api/photos/image/67c1e601be14dc12f6b266de.png",  # Monitor
    20: "https://eprodutos-integracao.microware.com.br/api/photos/image/67c1e621be14dc12f6b266e0.png",  # Notebook
    21: "https://eprodutos-integracao.microware.com.br/api/photos/image/67c1e66abe14dc12f6b266e2.png",  # Serviços
    22: "https://eprodutos-integracao.microware.com.br/api/photos/image/67c1e688be14dc12f6b266e4.png",  # SmartOffice
    23: "https://eprodutos-integracao.microware.com.br/api/photos/image/67c1e6bbbe14dc12f6b266e8.png",  # Workstation
    24: "https://eprodutos-integracao.microware.com.br/api/photos/image/67c1e69dbe14dc12f6b266e6.png"   # Tiny
}

def load_product_cache():
    """Carrega o cache de produtos do arquivo JSON"""
    global product_cache
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                product_cache = json.load(f)
    except Exception as e:
        print(f"Erro ao carregar cache: {str(e)}")
        product_cache = {}

def save_product_cache():
    """Salva o cache de produtos em um arquivo JSON"""
    try:
        # Garante que o diretório existe
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(product_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erro ao salvar cache: {str(e)}")

def processar_lenovo_data(lenovo_data):
    # Carrega o cache ao iniciar o processamento
    load_product_cache()
    
    global products_df
    products_df = pd.concat(lenovo_data.values(), ignore_index=True)
    
    if "STATE" in products_df.columns:
        products_df = products_df[products_df["STATE"].str.lower().str.strip() == "sp"]
    
    if "CUSTOMER_TYPE" in products_df.columns:
        products_df = products_df[products_df["CUSTOMER_TYPE"].str.lower().str.strip() == "revenda sem regime"]
    
    MANUFACTURE = "Lenovo"
    STOCK = 10
    MARGIN = 20 

    print("\nCarregando dados necessários...")
    images = buscar_imagens()
    delivery_info = buscar_delivery()
    normalized_family = normalize_values_list("Familia")
    normalized_anatel = normalize_values_list("Anatel")
    print("Dados carregados com sucesso!")

    total_produtos = len(products_df)
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Iniciando processamento de {total_produtos} produtos...", flush=True)
    
    combined_data = []
    for index, product in products_df.iterrows():
        # Log de progresso a cada 5 produtos
        if (index + 1) % 5 == 0 or index == 0:
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"[{timestamp}] Processando produto {index + 1}/{total_produtos} ({(index + 1)/total_produtos*100:.1f}%) - SKU: {product['PRODUCT_CODE']}", flush=True)
        
        categories_data = processar_categories(product)
        
        product_name = product['PRODUCT_DESCRIPTION']
        if product_name.startswith('NB'):
            product_name = product_name.replace('NB', 'Notebook', 1)
        
        shipping_class = "importado" if product['PART_ORIGIN'] == "IMPORTED" else "local"

        product_data = getProductBySKU(product['PRODUCT_CODE'])

        produto_data = {
            'name': product_name,
            'sku': product['PRODUCT_CODE'],
            'short_description': product['PH4_DESCRIPTION'],
            'description': product['PRODUCT_DESCRIPTION'],
            'price': str(product['UNIT_GROSS_PRICE(R$)'] * (1 + MARGIN / 100)),
            'regular_price': str(product['UNIT_GROSS_PRICE(R$)'] * (1 + MARGIN / 100)),
            'stock_quantity': 10,
            'manage_stock': True,
            'attributes': processar_attributes(product),
            'meta_data': processar_fotos(product, images, normalized_family, product_data),
            'dimensions': processar_dimensions(product, delivery_info, product_data),
            'weight': str(processar_weight(product, delivery_info, product_data)),
            'shipping_class': shipping_class
        }
        produto_data.update(categories_data)
        combined_data.append(produto_data)
    
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"\n[{timestamp}] Processamento concluído! Total de produtos processados: {len(combined_data)}", flush=True)
    #enviar_email(EmailProducts)
    return combined_data

def processar_categories(product):

    CATEGORY_MAPPING = {
        "Notebook": ["Notebook"],
        "Desktop": ["Desktop"],
        "Workstation": ["Workstation"],
        "Tablet Android": ["Tablet"],
        "Visuals": ["Display"],
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

    normalized_family = normalize_values_list("Familia")
    normalized_anatel = normalize_values_list("Anatel")
    family = normalized_family.get(product["PH4_DESCRIPTION"], "")
    anatel = normalized_anatel.get(family, "")
    if anatel:
        attributes.append({
            'id': 13,
            'options': str(anatel),
            'visible': True
        })
    else:
        EmailProducts.append(str(product['PRODUCT_CODE']) + " - " + "Produto sem codigo anatel")
    
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
                        if isinstance(atributo_existente['options'], str):
                            atributo_existente['options'] = [atributo_existente['options']]
                        atributo_existente['options'].append(valor)
                else:
                    # Se o atributo não existe, cria um novo
                    attributes.append({
                        'id': wp_attribute['id'],
                        'options': [str(valor)],
                        'visible': True
                    })
    
    attributes.append({
        'id': 68,
        'options': [str(product['PH4_DESCRIPTION'])],
        'visible': True
    })

    attributes.append({
        'id': 67,
        'options': ["Lenovo"],
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

def buscar_delivery():
    url = "https://eprodutos-integracao.microware.com.br/api/delivery-info/"
    response = requests.get(url)
    if response.status_code != 200:
        return []
    df = pd.DataFrame(response.json())
    return df

def get_default_photo(categories):
    """Retorna a foto padrão baseada na primeira categoria encontrada"""
    for category in categories:
        category_id = category.get('id')
        if category_id in DEFAULT_PHOTOS:
            return DEFAULT_PHOTOS[category_id]
    # Se não encontrar nenhuma categoria mapeada, retorna a foto padrão de acessório
    return DEFAULT_PHOTOS[17]

def processar_fotos(product, images, normalized_family, product_data):
    if not product_data:
        df = images
        base_url = "https://eprodutos-integracao.microware.com.br/api/photos/image/"
        filtered_df = pd.DataFrame()

        normalize_family = normalized_family.get(product["PH4_DESCRIPTION"], "")

        search_term = product.get("PH4_DESCRIPTION")

        for index, row in df.iterrows():
            if row['family'] in search_term:
                filtered_df = pd.concat([filtered_df, pd.DataFrame([row])])

        # Se não encontrar, tenta com a família Default
        if filtered_df.empty:
            filtered_df = df[
                (df['manufacturer'] == "Lenovo") & 
                (df['category'] == product['PH_BRAND']) & 
                (df['family'] == normalize_family)
            ]

        # Se ainda estiver vazio, tenta com a família Default
        if filtered_df.empty:
            CATEGORY_MAPPING = {
            "Notebook": ["Notebook"],
            "Desktop": ["Desktop"],
            "Workstation": ["Workstation"],
            "Tablet Android": ["Tablet"],
            "Visuals": ["Monitor"],
            "Smart Office": ["SmartOffice"]
            }

            default_category = CATEGORY_MAPPING.get(product['PH_BRAND'], ["Acessório"])
            
            for index, row in df.iterrows():
                if row['category'] in default_category and row['manufacturer'] == "Lenovo" and row['family'] == "Default":
                    filtered_df = pd.concat([filtered_df, pd.DataFrame([row])])
                    EmailProducts.append(str(product['PRODUCT_CODE']) + " - " + "Produto com foto default")

        # Cria a lista de URLs das imagens
        image_urls = []
        for _, row in filtered_df.iterrows():
            if 'id' in row and 'extension' in row:
                image_url = f"{base_url}{row['id']}.{row['extension']}"
                image_urls.append(image_url)

        # Se não encontrou imagens, usa foto padrão baseada na categoria
        if not image_urls:
            categories_data = processar_categories(product)
            default_photo = get_default_photo(categories_data.get('categories', []))
            meta_data = [
                {
                    "key": "_external_image_url",
                    "value": default_photo
                }
            ]
            EmailProducts.append(str(product['PRODUCT_CODE']) + " - " + "Produto usando foto padrão da categoria")
            return meta_data

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
    else:
        return process_api_photos(product_data)

def processar_dimensions(product, delivery_info, product_data):
    if product_data:
        return process_api_dimensions(product_data)
    else:
        try:
            normalized_family = normalize_values_list("Familia")
            family = normalized_family.get(product["PH4_DESCRIPTION"], "")
            delivery_info = delivery_info[delivery_info["family_code"] == family]
            if not delivery_info.empty:
                dimensions = delivery_info.iloc[0]
                return {
                    "length": dimensions["depth"],
                    "width": dimensions["width"],
                    "height": dimensions["height"]
                }
            else:
                EmailProducts.append(str(product['PRODUCT_CODE']) + " - " + "Produto sem dimensões")
                return {
                    "length": 2.1,
                    "width": 2.1,
                    "height": 2.1
                }

        except Exception as e:
            print(f"Erro ao processar informações de entrega: {str(e)}")
            return []

def process_api_weight(product_data):
    if not product_data:
        EmailProducts.append("Produto não encontrado na API Lenovo")
        return "1.0"  # Retorna 1kg como padrão em string
    
    try:
        spec_data = product_data.get('data', {}).get('SpecData', [])
        
        def extract_weight(weight_text):
            # Remove caracteres especiais e marcações
            clean_text = re.sub(r'[®™]', '', weight_text)
            
            # Padrão para encontrar peso em kg
            kg_pattern = r'(\d+\.?\d*)\s*kg'
            # Padrão para encontrar peso em gramas
            g_pattern = r'(\d+\.?\d*)\s*g'
            
            # Tenta encontrar peso em kg primeiro
            kg_match = re.search(kg_pattern, clean_text)
            if kg_match:
                return str(float(kg_match.group(1)))  # Já está em kg, converte para string
            
            # Se não encontrar em kg, tenta em gramas e converte para kg
            g_match = re.search(g_pattern, clean_text)
            if g_match:
                return str(float(g_match.group(1)) / 1000)  # Converte gramas para kg e para string
            
            return None

        # Procura o campo Weight
        weight_entry = next((item for item in spec_data if item.get('name') == 'Weight'), None)
        if not weight_entry or not weight_entry.get('content'):
            EmailProducts.append("Peso não encontrado na API Lenovo")
            return "1.0"  # Retorna 1kg como padrão em string

        # Se tiver múltiplos pesos (como no caso do ThinkSmart)
        if len(weight_entry['content']) > 1:
            # Pega o primeiro peso da lista (geralmente o principal)
            first_weight = weight_entry['content'][0]
            # Extrai apenas a parte do peso (ignora o nome do produto)
            weight_part = first_weight.split('|')[-1].strip()
            weight = extract_weight(weight_part)
            if weight:
                return weight
        else:
            # Caso normal com um único peso
            weight_text = weight_entry['content'][0]
            
            # Trata caso especial de múltiplos pesos somados
            if '+' in weight_text:
                total_weight = 0
                for part in weight_text.split('+'):
                    weight = extract_weight(part)
                    if weight:
                        total_weight += float(weight)
                if total_weight > 0:
                    return str(total_weight)
            
            # Caso normal
            weight = extract_weight(weight_text)
            if weight:
                return weight

        # Se não encontrou nenhum peso válido
        EmailProducts.append("Peso não encontrado ou inválido na API Lenovo")
        return "1.0"  # Retorna 1kg como padrão em string

    except Exception as e:
        print(f"Erro ao processar peso da API Lenovo: {str(e)}")
        EmailProducts.append(f"Erro ao processar peso da API Lenovo: {str(e)}")
        return "1.0"  # Retorna 1kg como padrão em string

def processar_weight(product, delivery_info, product_data):
    if product_data:
        return process_api_weight(product_data)
    else:
        try:
            normalized_family = normalize_values_list("Familia")
            family = normalized_family.get(product["PH4_DESCRIPTION"], "")
            delivery_info = delivery_info[delivery_info["family_code"] == family]
            if not delivery_info.empty:
                dimensions = delivery_info.iloc[0]
                return str(dimensions["weight"])  # Converte para string
           
            else:
                EmailProducts.append(str(product['PRODUCT_CODE']) + " - " + "Produto sem peso")
                return "1.0"  # Retorna 1kg como padrão em string

        except Exception as e:
            print(f"Erro ao processar informações de entrega: {str(e)}")
            return "1.0"  # Retorna 1kg como padrão em string

def normalize_values_list(value):
    # Verifica se o valor já está no cache
    if value in normalized_values_cache:
        return normalized_values_cache[value]
    
    normalize_values_list = []
    request = requests.get(f"https://eprodutos-integracao.microware.com.br/api/normalize-values")
    if request.status_code == 200:
        response_data = request.json()
        for item in response_data:
            if item["column"] == value:
                normalize_values_list = item["from_to"]
                # Armazena no cache
                normalized_values_cache[value] = normalize_values_list
                break
    return normalize_values_list

def enviar_email(email_products):
    servidor_smtp = "smtp.microware.com.br"
    porta = 25  
    email_origem = "maycon.jardim@microware.com.br"
    email_destino = "maycon.jardim@microware.com.br"
    assunto = "Nova lista de produtos Lenovo enviada para o Ecommerce!"

    # Agrupar informações por SKU
    produtos_agrupados = {}
    for produto in email_products:
        sku = produto.split(" - ")[0]
        problema = produto.split(" - ")[1]
        if sku not in produtos_agrupados:
            produtos_agrupados[sku] = []
        produtos_agrupados[sku].append(problema)

    # Montar o corpo do e-mail
    corpo = "Segue informações de produtos sem alguns dados:\n\n"
    for sku, problemas in produtos_agrupados.items():
        corpo += f"SKU: {sku}\n"
        corpo += "Problemas encontrados:\n"
        for problema in problemas:
            corpo += f"  - {problema}\n"
        corpo += "\n"

    # Criar a mensagem
    mensagem = MIMEMultipart()
    mensagem['From'] = email_origem
    mensagem['To'] = email_destino
    mensagem['Subject'] = assunto
    mensagem.attach(MIMEText(corpo, 'plain'))

    try:
        # Conectar e enviar
        servidor = smtplib.SMTP(servidor_smtp, porta)
        servidor.sendmail(email_origem, email_destino, mensagem.as_string())
        print("E-mail enviado com sucesso!")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
    finally:
        servidor.quit()


def getProductBySKU(sku):
    # Verifica se o produto já está no cache
    if sku in product_cache:
        return product_cache[sku]

    hora = datetime.now().strftime("%Y%m%d%H%M%S")
    
    url = f"https://psref.lenovo.com/api/model/Info/SpecData?model_code={sku}&t={hora}"
    response = requests.get(url)
    if response.status_code == 200:
        product_data = response.json()
        
        # Verifica se o produto foi encontrado
        if isinstance(product_data, dict) and product_data.get('code') == 0 and product_data.get('msg') == "No corresponding product found":
            product_cache[sku] = None  # Armazena None no cache para produtos não encontrados
            save_product_cache()
            return None
            
        # Armazena no cache antes de retornar
        product_cache[sku] = product_data
        save_product_cache()
        return product_data
    else:
        product_cache[sku] = None  # Armazena None no cache para produtos não encontrados
        save_product_cache()
        return None

def process_api_photos(product_data):
    if not product_data:  # Agora verifica se product_data é None
        EmailProducts.append("Produto não encontrado na API Lenovo")
        # Busca o produto no DataFrame para usar foto padrão
        if 'products_df' in globals():
            product_row = products_df[products_df['PRODUCT_CODE'] == product_data.get('data', {}).get('ModelCode', '')]
            if not product_row.empty:
                product = product_row.iloc[0]
                categories_data = processar_categories(product)
                default_photo = get_default_photo(categories_data.get('categories', []))
                return [{
                    "key": "_external_image_url",
                    "value": default_photo
                }]
        # Se não encontrar no DataFrame, usa foto padrão de acessório
        return [{
            "key": "_external_image_url",
            "value": DEFAULT_PHOTOS[17]  # Foto padrão de acessório
        }]

    try:
        # Obtém o array de URLs das imagens
        image_urls = product_data.get('data', {}).get('ProductPicturePathArray', [])
        
        if not image_urls:
            sku = product_data.get('data', {}).get('ModelCode', '')
            if not sku or 'products_df' not in globals():
                # Se não encontrar o SKU ou o DataFrame, usa foto padrão de acessório
                return [{
                    "key": "_external_image_url",
                    "value": DEFAULT_PHOTOS[17]
                }]

            # Busca o produto no DataFrame
            product_row = products_df[products_df['PRODUCT_CODE'] == sku]
            if product_row.empty:
                # Se não encontrar o produto, usa foto padrão de acessório
                return [{
                    "key": "_external_image_url",
                    "value": DEFAULT_PHOTOS[17]
                }]

            product = product_row.iloc[0]
            
            # Verifica a categoria para usar foto padrão
            categories_data = processar_categories(product)
            default_photo = get_default_photo(categories_data.get('categories', []))
            meta_data = [
                {
                    "key": "_external_image_url",
                    "value": default_photo
                }
            ]
            EmailProducts.append(f"{sku} - Produto usando foto padrão da categoria (API)")
            return meta_data

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

    except Exception as e:
        print(f"Erro ao processar fotos da API Lenovo: {str(e)}")
        EmailProducts.append(f"Erro ao processar fotos da API Lenovo: {str(e)}")
        # Em caso de erro, retorna foto padrão de acessório
        return [{
            "key": "_external_image_url",
            "value": DEFAULT_PHOTOS[17]
        }]

def process_api_dimensions(product_data):
    if not product_data:
        EmailProducts.append("Produto não encontrado na API Lenovo")
        return {
            "length": 2.1,
            "width": 2.1,
            "height": 2.1
        }
    
    try:
        spec_data = product_data.get('data', {}).get('SpecData', [])
        
        def extract_dimensions(dimensions_text):
            # Remove caracteres especiais e marcações
            clean_text = re.sub(r'[®™]', '', dimensions_text)
            
            # Padrão para encontrar dimensões no formato "XXX x YYY x ZZZ mm"
            pattern = r'(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*mm'
            match = re.search(pattern, clean_text)
            
            if match:
                width = float(match.group(1))
                depth = float(match.group(2))
                height = float(match.group(3))
                return {
                    "length": depth / 10,  # Converte mm para cm
                    "width": width / 10,
                    "height": height / 10
                }
            return None

        # Primeiro tenta encontrar Packaging Dimensions
        packaging_dimensions = next((item for item in spec_data if item.get('name') == 'Packaging Dimensions (WxDxH)'), None)
        if packaging_dimensions and packaging_dimensions.get('content'):
            dimensions = extract_dimensions(packaging_dimensions['content'][0])
            if dimensions:
                return dimensions

        # Se não encontrar Packaging Dimensions, procura Dimensions (WxDxH)
        product_dimensions = next((item for item in spec_data if item.get('name') == 'Dimensions (WxDxH)'), None)
        if product_dimensions and product_dimensions.get('content'):
            # Se tiver múltiplas dimensões (como no caso do ThinkSmart)
            if len(product_dimensions['content']) > 1:
                # Pega a última dimensão da lista
                last_dimension = product_dimensions['content'][-1]
                # Extrai apenas a parte das dimensões (ignora o nome do produto)
                dimension_part = last_dimension.split('|')[-1].strip()
                dimensions = extract_dimensions(dimension_part)
                if dimensions:
                    return dimensions
            else:
                # Caso normal com uma única dimensão
                dimensions = extract_dimensions(product_dimensions['content'][0])
                if dimensions:
                    return dimensions

        # Se não encontrou nenhuma dimensão válida
        EmailProducts.append("Dimensões não encontradas ou inválidas na API Lenovo")
        return {
            "length": 2.1,
            "width": 2.1,
            "height": 2.1
        }

    except Exception as e:
        print(f"Erro ao processar dimensões da API Lenovo: {str(e)}")
        EmailProducts.append(f"Erro ao processar dimensões da API Lenovo: {str(e)}")
        return {
            "length": 2.1,
            "width": 2.1,
            "height": 2.1
        }

