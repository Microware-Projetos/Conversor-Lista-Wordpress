import pandas as pd
import io
import sys
import os
import json
import requests
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Cache global para valores normalizados
normalized_values_cache = {}
EmailProducts = []

def processar_hp_data(produtos, precos):
    df_produtos = ler_arquivo_produto_hp(produtos)
    df_precos = ler_arquivo_preco_hp(precos)

    combined_data = combinar_dados(df_produtos, df_precos)
    
    return combined_data

def combinar_dados(df_produtos, df_precos):
    combined_data = []

    images = buscar_imagens()
    delivery = buscar_delivery()
    normalized_family = normalize_values_list("Familia")
    normalized_anatel = normalize_values_list("Anatel")

    # Para cada produto na lista de dicionários
    for product in df_produtos:
       
        if product.get("sheet_name") == "SmartChoice":  
            # Pular o produto se o PN estiver vazio
            if "PN" not in product or pd.isna(product["PN"]):
                continue

            # Encontrar o preço correspondente
            price_info = df_precos[df_precos["SKU"] == product["PN"]]

            # Pular o produto se o PN não existir na lista de preços
            if len(price_info) == 0:
                continue
            
            price_info = price_info.iloc[0]
            price_por = price_info["Preço Bundle R$"] / (1 - (20 / 100)) if price_info is not None else None

            produto_data = {
                'name': str(product.get("SmartChoice", "")) + " " + str(product.get("Descrição", "")),
                'sku': product["PN"],
                'short_description': product.get("Descrição", ""),
                'price': price_por,
                'regular_price': price_por,
                'stock_quantity': 100,
                'attributes': processar_attributes(product),
                'meta_data': processar_fotos(product, images, normalized_family),
                'dimmensions': processar_dimmensions(product, delivery),
                'weight': processar_weight(product, delivery),
                'categories': processar_categories(product, "SmartChoice")
            }
            
        elif product.get("sheet_name") == "Portfólio Acessorios_Monitores":
            # Pular o produto se o SKU estiver vazio
            if "SKU" not in product or pd.isna(product["SKU"]):
                    continue

            # Encontrar o preço correspondente
            price_info = df_precos[df_precos["SKU"] == product["SKU"]]

            # Pular o produto se o SKU não existir na lista de preços
            if len(price_info) == 0:
                continue
            
            price_info = price_info.iloc[0]
            price_por = price_info["Preço Bundle R$"] / (1 - (20 / 100)) if price_info is not None else None

            pl_group = str(product.get("PL GROUP", "")).lower()
            categoria = "Display" if "display" in pl_group else "Acessório"
            
            produto_data = {
                'name': str(product.get("DESCRIÇÃO", "")),
                'sku': product["SKU"],
                'short_description': product.get("Descrição", ""),
                'price': price_por,
                'regular_price': price_por,
                'stock_quantity': 100,
                'attributes': processar_attributes(product),
                'meta_data': processar_fotos(product, images, normalized_family),
                'dimmensions': processar_dimmensions(product, delivery),
                'weight': processar_weight(product, delivery),
                'categories': processar_categories(product, categoria)
            }
        
        else :

            # Pular o produto se o SKU estiver vazio
            if "SKU" not in product or pd.isna(product["SKU"]):
                    continue

            # Encontrar o preço correspondente
            price_info = df_precos[df_precos["SKU"] == product["SKU"]]

            # Pular o produto se o SKU não existir na lista de preços
            if len(price_info) == 0:
                continue
        
            # Converter o sheet_name usando o mapeamento
            with open('HP/maps/map.json', 'r') as f:
                rename = json.load(f).get("TraducaoLinha", {})
            product_type = rename.get(product["sheet_name"], product["sheet_name"])

            price_info = price_info.iloc[0]
            price_por = price_info["Preço Bundle R$"] / (1 - (20 / 100)) if price_info is not None else None

            descricao = ""
            if product_type == "Notebook":
                descricao = product_type + " " + str(product.get("Model", "")) + " " + str(product.get("Processor", "")) + " " + str(product.get("OS", "")) + " " + str(product.get("Memory", "")) + " " + str(product.get("Internal Storage","" ))
            elif product_type == "Desktop":
                      descricao = product_type + " " + str(product.get("Model", "")) + " " + str(product.get("Processor", "")) + " " + str(product.get("OS", "")) + " " + str(product.get("Memory", "")) + " " + str(product.get("Internal Storage 1","" ))
            elif product_type == "Mobile":
                      descricao = product_type + " " + str(product.get("Model", "")) + " " + str(product.get("Processor", "")) + " " + str(product.get("OS", "")) + " " + str(product.get("Memory", "")) + " " + str(product.get("Primary Storage Drive","" ))
            elif product_type == "Workstation":
                    descricao = product_type + " " + str(product.get("Model", "")) + " " + str(product.get("Processor", "")) + " " + str(product.get("OS", "")) + " " + str(product.get("Memory", "")) + " " + str(product.get("Storage - Hard Drive 1","" ))
            elif product_type == "Thin Client":
                    descricao = product_type + " " + str(product.get("Model", "")) + " " + str(product.get("Processador", "")) + " " + str(product.get("OS", "")) + " " + str(product.get("RAM (MB)", "")) + " " + str(product.get("FLASH (GF)","" ))


            produto_data = {
                'name': product_type + " " + product["Model"],
                'sku': product["SKU"],
                'short_description': descricao,
                'price': price_por,
                'regular_price': price_por,
                'stock_quantity': 100,
                'attributes': processar_attributes(product),
                'meta_data': processar_fotos(product, images, normalized_family),
                'dimmensions': processar_dimmensions(product, delivery),
                'weight': processar_weight(product, delivery),
                'categories': processar_categories(product, product_type)
            }

        combined_data.append(produto_data)
    

    
    # Converter os dados combinados para JSON e salvar na pasta
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'produtos_processados_hp.json')
    with open(output_path, 'w', encoding='utf-8') as json_file:
        json.dump(combined_data, json_file, ensure_ascii=False, indent=4)
    
    enviar_email(EmailProducts)
    return combined_data

def ler_arquivo_produto_hp(product_file):
    contents = product_file.read()
    product_excel = io.BytesIO(contents)
    
    # Obter todas as planilhas
    excel_sheets = pd.read_excel(product_excel, sheet_name=None)
    # Remover primeira e última planilha
    sheet_names = list(excel_sheets.keys())[1:-1]
    
    all_products = []
    # Processar cada planilha separadamente
    for sheet_name in sheet_names:
        # Resetar o ponteiro do arquivo
        product_excel.seek(0)
        # Ler planilha com cabeçalho na segunda linha
        df = pd.read_excel(product_excel, sheet_name=sheet_name, header=1)
        
        # Converter cada linha para um dicionário usando os cabeçalhos das colunas
        for _, row in df.iterrows():
            product_dict = {}
            product_dict['sheet_name'] = sheet_name  # Adicionar nome da planilha ao dicionário
            for column in df.columns:
                if pd.notna(row[column]):  # Incluir apenas valores não nulos
                    product_dict[column] = row[column]
            if product_dict:  # Adicionar apenas se o dicionário não estiver vazio
                all_products.append(product_dict)
    
    return all_products

def ler_arquivo_preco_hp(price_file):
    contents = price_file.read()
    price_excel = io.BytesIO(contents)
    price_df = pd.read_excel(price_excel, sheet_name="SP")
    return price_df

def processar_attributes(product):
    attributes = []
    with open('HP/maps/map.json', 'r') as f:
        map_data = json.load(f)
        colunas_mapping = map_data["Colunas"]
        attributes_mapping = map_data["Attributes"]

    with open('HP/maps/atributes.json', 'r') as f:
        attributes_mapping_wp = json.load(f)

    sheet_name = product["sheet_name"]
    coluna = ""
    if sheet_name == "SmartChoice":
        coluna = "PN"
    elif sheet_name == "Portfólio Acessorios_Monitores":
        coluna = "SKU"
    else:
        coluna = "Model"

    normalized_family = normalize_values_list("Familia")
    normalized_anatel = normalize_values_list("Anatel")
    family = normalized_family.get(product[coluna], "") 
    anatel = normalized_anatel.get(family, "")
    if anatel:
        attributes.append({
            'id': 13,
            'options': anatel,
            'visible': True
        })
    else:
        family = product.get("Model", "").split(' ', 1)[1].lstrip() if ' ' in product.get("Model", "") else product.get("Model", "")
        family = family.strip()
        if family.lower().startswith("hp "):
            family = family[3:]
        
        anatel = normalized_anatel.get(family, "")
        if anatel:
            attributes.append({
                'id': 13,
                'options': anatel,
                'visible': True
            })
        else:
            EmailProducts.append(str(product[coluna]) + " - " + "Produto sem codigo anatel")


    for hp_key in product:
        # Encontra o valor correspondente em Colunas
        if hp_key in colunas_mapping:
            coluna_value = colunas_mapping[hp_key]
            
            # Se o valor for "attributes", procura o nome do atributo em Attributes
            if coluna_value == "attributes" and hp_key in attributes_mapping:
                attribute_name = attributes_mapping[hp_key]
                
                # Encontra o ID correspondente no attributesWordpress
                wp_attribute = next((attr for attr in attributes_mapping_wp if attr['name'] == attribute_name), None)

                if wp_attribute:
                    # Converte o valor para string e remove valores NaN
                    valor = str(product[hp_key])
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

    attributes.append({
        'id': 45,
        'options': ["HP"],
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
    sheet_name = product["sheet_name"]
    coluna = ""
    if sheet_name == "SmartChoice":
        coluna = "PN"
    elif sheet_name == "Portfólio Acessorios_Monitores":
        coluna = "SKU"
    else:
        coluna = "Model"

    df = images
    base_url = "https://eprodutos-integracao.microware.com.br/api/photos/image/"
    filtered_df = pd.DataFrame()
    
    normalize_family = normalized_family.get(product.get("Model", ""), product.get("Descrição", product.get("DESCRIÇÃO", ""))) 
    sheet_name = product["sheet_name"]
    category = json.load(open('HP/maps/map.json'))['TraducaoLinha'].get(sheet_name, "Acessorio")

    search_term = product.get("Model") or product.get("Descrição") or product.get("DESCRIÇÃO") or ""

    for index, row in df.iterrows():
        if isinstance(row['family'], str) and row['family'] in search_term:
            filtered_df = pd.concat([filtered_df, pd.DataFrame([row])])

    # Se não encontrar, tenta com a família Default
    if filtered_df.empty:
        filtered_df = df[
            (df['manufacturer'] == "HP") & 
            (df['category'] == category) & 
            (df['family'] == normalize_family)
        ]

    # Se ainda estiver vazio, tenta com a família Default
    if filtered_df.empty:
        if sheet_name == "Portfólio Acessorios_Monitores":
            pl_group = str(product.get("PL GROUP", "")).lower()
            default_category = "Monitor" if "display" in pl_group else "Acessorio"
        else:
            default_category = json.load(open('HP/maps/map.json'))['DefaultPhotos'].get(sheet_name, "Acessorio")
        
        for index, row in df.iterrows():
            if isinstance(row['category'], str) and row['category'] in default_category and row['manufacturer'] == "HP" and row['family'] == "Default":
                filtered_df = pd.concat([filtered_df, pd.DataFrame([row])])
                EmailProducts.append(str(product[coluna]) + " - " + "Produto com foto default")
        
    # Cria a lista de URLs das imagens
    image_urls = []
    for _, row in filtered_df.iterrows():
        if 'id' in row and 'extension' in row:
            image_url = f"{base_url}{row['id']}.{row['extension']}"
            image_urls.append(image_url)

    if not image_urls:
        EmailProducts.append(str(product[coluna]) + " - " + "Produto sem foto")
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

def processar_categories(product, categoria):
 
    categories = []
    with open('HP/maps/categoriesWordpress.json', 'r') as f:
        categories_mapping = json.load(f)
    
    for category in categories_mapping:
        if category['name'] == categoria:
            categories.append({"id": category['id']})
            break
    
    # Garante que sempre tenha pelo menos uma categoria
    if not categories:
        # Adiciona "Acessório" como categoria padrão
        for category in categories_mapping:
            if category['name'] == "Acessório":
                categories.append({"id": category['id']})
                break

    return categories

def processar_dimmensions(product, delivery_info):
    try:
        sheet_name = product["sheet_name"]
        coluna = ""
        if sheet_name == "SmartChoice":
            coluna = "PN"
        elif sheet_name == "Portfólio Acessorios_Monitores":
            coluna = "SKU"
        # Obtém a família normalizada
        normalized_family = normalize_values_list("Familia")
        family = normalized_family.get(
            product.get("Model", ""), 
            product.get("Descrição", product.get("DESCRIÇÃO", ""))
        )
        
        # Tenta obter dimensões do delivery_info
        delivery_info_filtered = delivery_info[delivery_info["family_code"] == family]
        
        if not delivery_info_filtered.empty:
            dimmensions = delivery_info_filtered.iloc[0]
            return {
                "length": float(dimmensions["depth"]),  
                "width": float(dimmensions["width"]),   
                "height": float(dimmensions["height"])  
            }

        # Fallback para produtos que não são SmartChoice, Acessórios/Monitores ou Thin Clients
        elif product.get("sheet_name") not in ["SmartChoice", "Portfólio Acessorios_Monitores", "Thin Clients"]:
            product_dimensions = product.get("Dimension", "")
            if product_dimensions:
                try:
                    # Remove "cm" e espaços extras
                    dimensions_str = product_dimensions.lower().replace("cm", "").strip()
                    # Substitui vírgulas por pontos
                    dimensions_str = dimensions_str.replace(",", ".")
                    # Remove espaços extras entre números e 'x'
                    dimensions_str = re.sub(r'\s*x\s*', 'x', dimensions_str)
                    
                    # Divide as dimensões
                    dimensions = [float(dim.strip()) for dim in dimensions_str.split("x")]
                    
                    if len(dimensions) == 3:
                        return {
                            "length": dimensions[0],  
                            "width": dimensions[1],   
                            "height": dimensions[2]   
                        }
                except (ValueError, AttributeError) as e:
                    print(f"Erro ao processar dimensões: {str(e)} para o valor: {product_dimensions}")
                    pass
        
        # Retorna dimensões padrão mínimas para o WooCommerce
            EmailProducts.append(str(product[coluna]) + " - " + "Produto sem dimensoes")
        return {
            "length": 0.1,  # 10cm
            "width": 0.1,
            "height": 0.1
        }

    except Exception as e:
        print(f"Erro ao processar dimensões: {str(e)}")
        EmailProducts.append(str(product[coluna]) + " - " + "Produto sem dimensoes")
        return {
            "length": 0.1,
            "width": 0.1,
            "height": 0.1
        }

def processar_weight(product, delivery_info):
    try:
        sheet_name = product.get("sheet_name", "")
        coluna = ""
        if sheet_name == "SmartChoice":
            coluna = "PN"
        elif sheet_name == "Portfólio Acessorios_Monitores":
            coluna = "SKU"
        else:
            coluna = "SKU"  # Valor padrão caso não seja nenhum dos casos acima
            
        # Obtém a família normalizada
        normalized_family = normalize_values_list("Familia")
        family = normalized_family.get(
            product.get("Model", ""), 
            product.get("Descrição", product.get("DESCRIÇÃO", ""))
        )
        
        # Tenta obter peso do delivery_info
        delivery_info_filtered = delivery_info[delivery_info["family_code"] == family]
        
        if not delivery_info_filtered.empty:
            weight = delivery_info_filtered.iloc[0]["weight"]
            return float(weight) if weight is not None else 0.1

        # Fallback para produtos que não são SmartChoice, Acessórios/Monitores ou Thin Clients
        elif product.get("sheet_name") not in ["SmartChoice", "Portfólio Acessorios_Monitores", "Thin Clients"]:
            weight_raw = product.get("Weight", "")
            if weight_raw:
                try:
                    # Remove "kg", "Kg", " KG" etc. e troca vírgula por ponto
                    weight_cleaned = (
                        weight_raw.lower()
                        .replace("kg", "")
                        .replace(",", ".")
                        .strip()
                    )
                    return float(weight_cleaned)
                except ValueError as ve:
                    print(f"Erro ao converter peso: {str(ve)} para o valor: {weight_raw}")
                    pass
        
        # Retorna peso padrão mínimo para o WooCommerce
        sku = product.get(coluna, "SKU não encontrado")
        EmailProducts.append(f"{sku} - Produto sem peso")
        return 0.1  # 100g

    except Exception as e:
        sku = product.get(coluna, "SKU não encontrado")
        print(f"Erro ao processar peso para SKU {sku}: {str(e)}")
        EmailProducts.append(f"{sku} - Produto sem peso")
        return 0.1

def enviar_email(email_products):
    servidor_smtp = "smtp.microware.com.br"
    porta = 25  
    email_origem = "ecommerce@microware.com.br"
    email_destino = "ecommerce@microware.com.br"
    assunto = "Nova lista de produtos HP enviada para o Ecommerce!"

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
