import pandas as pd
import json
import requests
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


EmailProducts = []
normalized_values_cache = {}

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
    delivery_info = buscar_delivery()
    normalized_family = normalize_values_list("Familia")
    normalized_anatel = normalize_values_list("Anatel")

    combined_data = []
    for _, product in products_df.iterrows():
        categories_data = processar_categories(product)
        
        product_name = product['PRODUCT_DESCRIPTION']
        if product_name.startswith('NB'):
            product_name = product_name.replace('NB', 'Notebook', 1)
        
        produto_data = {
            'name': product_name,
            'sku': product['PRODUCT_CODE'],
            'short_description': product['PH4_DESCRIPTION'],
            'description': product['PRODUCT_DESCRIPTION'],
            'price': str(product['UNIT_GROSS_PRICE(R$)'] * (1 + MARGIN / 100)),
            'regular_price': str(product['UNIT_GROSS_PRICE(R$)'] * (1 + MARGIN / 100)),
            'stock_quantity': 100,
            'manage_stock': True,
            'attributes': processar_attributes(product),
            'meta_data': processar_fotos(product, images, normalized_family),
            'dimmensions': processar_dimmensions(product, delivery_info),
            'weight': processar_weight(product, delivery_info)
        }
        produto_data.update(categories_data)
        combined_data.append(produto_data)
    

    enviar_email(EmailProducts)
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
            'options': anatel,
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
                        'options': [valor],
                        'visible': True
                    })
    
    attributes.append({
        'id': 49,
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

def processar_fotos(product, images, normalized_family):
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


        

    # Se ainda estiver vazio, retorna meta_data vazio
    if filtered_df.empty:
        EmailProducts.append(str(product['PRODUCT_CODE']) + " - " + "Produto sem foto")
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


def processar_dimmensions(product, delivery_info):
        try:
            normalized_family = normalize_values_list("Familia")
            family = normalized_family.get(product["PH4_DESCRIPTION"], "")
            delivery_info = delivery_info[delivery_info["family_code"] == family]
            if not delivery_info.empty:
                dimmensions = delivery_info.iloc[0]
                return {
                    "length": dimmensions["depth"],
                    "width": dimmensions["width"],
                    "height": dimmensions["height"]
                }
            else:
                EmailProducts.append(str(product['PRODUCT_CODE']) + " - " + "Produto sem dimensões")
                return {
                    "length": 0.1,
                    "width": 0.1,
                    "height": 0.1
                }

        except Exception as e:
            print(f"Erro ao processar informações de entrega: {str(e)}")
            return []

def processar_weight(product, delivery_info):
    try:
        
            normalized_family = normalize_values_list("Familia")
            family = normalized_family.get(product["PH4_DESCRIPTION"], "")
            delivery_info = delivery_info[delivery_info["family_code"] == family]
            if not delivery_info.empty:
                dimmensions = delivery_info.iloc[0]
                return dimmensions["weight"]
           
            else:
                EmailProducts.append(str(product['PRODUCT_CODE']) + " - " + "Produto sem peso")
                return 0

    except Exception as e:
            print(f"Erro ao processar informações de entrega: {str(e)}")
            return []

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



