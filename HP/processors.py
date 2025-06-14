import pandas as pd
import io
import sys
import os
import json
import requests
import re
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Diretório para armazenar o cache
CACHE_DIR = "HP/cache"
PRODUCT_CACHE_FILE = os.path.join(CACHE_DIR, "product_cache.json")
ATTRIBUTES_CACHE_FILE = os.path.join(CACHE_DIR, "attributes_cache.json")
CACHE_EXPIRY_DAYS = 300  # Tempo em dias para expirar o cache

def ensure_cache_dir():
    """Garante que o diretório de cache existe"""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

def load_cache(cache_file):
    """Carrega o cache do arquivo"""
    if not os.path.exists(cache_file):
        return {}
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
            # Limpa itens expirados
            current_time = datetime.now()
            cache_data = {k: v for k, v in cache_data.items() 
                         if datetime.fromisoformat(v['timestamp']) + timedelta(days=CACHE_EXPIRY_DAYS) > current_time}
            return cache_data
    except Exception as e:
        print(f"Erro ao carregar cache: {str(e)}")
        return {}

def save_cache(cache_file, cache_data):
    """Salva o cache no arquivo"""
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erro ao salvar cache: {str(e)}")

def get_cached_data(sku, cache_file):
    """Obtém dados do cache se disponível e não expirado"""
    cache_data = load_cache(cache_file)
    if sku in cache_data:
        cache_entry = cache_data[sku]
        cache_time = datetime.fromisoformat(cache_entry['timestamp'])
        if datetime.now() - cache_time < timedelta(days=CACHE_EXPIRY_DAYS):
            return cache_entry['data']
    return None

def save_to_cache(sku, data, cache_file):
    """Salva dados no cache"""
    cache_data = load_cache(cache_file)
    cache_data[sku] = {
        'data': data,
        'timestamp': datetime.now().isoformat()
    }
    save_cache(cache_file, cache_data)

# Cache global para valores normalizados
normalized_values_cache = {}
EmailProducts = []

def processar_hp_data(produtos, precos):
    print("\nIniciando processamento dos arquivos HP...")
    try:
        print("Lendo arquivo de produtos...")
        df_produtos = ler_arquivo_produto_hp(produtos)
        print(f"Arquivo de produtos lido com sucesso. Total de produtos: {len(df_produtos)}")
        
        print("\nLendo arquivo de preços...")
        df_precos = ler_arquivo_preco_hp(precos)
        print(f"Arquivo de preços lido com sucesso. Total de preços: {len(df_precos)}")
        
        print("\nIniciando combinação dos dados...")
        combined_data = combinar_dados(df_produtos, df_precos)
        print("Combinação de dados concluída com sucesso!")
        
        return combined_data
    except Exception as e:
        print(f"\nERRO CRÍTICO em processar_hp_data:")
        print(f"Tipo do erro: {type(e).__name__}")
        print(f"Mensagem do erro: {str(e)}")
        raise

def combinar_dados(df_produtos, df_precos):
    print("\nIniciando combinar_dados...")
    print(f"Total de produtos a processar: {len(df_produtos)}")
    print(f"Total de preços disponíveis: {len(df_precos)}")
    
    combined_data = []
    contador = 0
    total_produtos = len(df_produtos)

    print("\nCarregando dados auxiliares...")
    try:
        print("Buscando imagens...")
        images = buscar_imagens()
        print(f"Total de imagens encontradas: {len(images)}")
        
        print("\nBuscando informações de delivery...")
        delivery = buscar_delivery()
        print(f"Total de informações de delivery encontradas: {len(delivery)}")
        
        print("\nNormalizando valores de família...")
        normalized_family = normalize_values_list("Familia")
        print(f"Total de famílias normalizadas: {len(normalized_family)}")
        
        print("\nNormalizando valores Anatel...")
        normalized_anatel = normalize_values_list("Anatel")
        print(f"Total de valores Anatel normalizados: {len(normalized_anatel)}")
        
        print("\nDados auxiliares carregados com sucesso!")
    except Exception as e:
        print(f"\nERRO ao carregar dados auxiliares:")
        print(f"Tipo do erro: {type(e).__name__}")
        print(f"Mensagem do erro: {str(e)}")
        raise

    print("\nIniciando processamento dos produtos...")
    # Para cada produto na lista de dicionários
    for product in df_produtos:
        contador += 1
        print(f"\nProcessando produto {contador} de {total_produtos}")
        
        try:
            # Identificar o produto atual
            sku = product.get("SKU", product.get("PN", "SKU/PN não encontrado"))
            print(f"Processando SKU/PN: {sku}")
            print(f"Tipo de produto: {product.get('sheet_name', 'Não especificado')}")
            
            # Log dos dados do produto para debug
            print("Dados do produto:")
            for key, value in product.items():
                if isinstance(value, (str, int, float, bool)):
                    print(f"  {key}: {value}")
                else:
                    print(f"  {key}: {type(value)}")
           
            if product.get("sheet_name") == "SmartChoice":  
                # Pular o produto se o PN estiver vazio
                if "PN" not in product or pd.isna(product["PN"]):
                    continue

                product_info = getProductBySKU(product["PN"])
                if not product_info:
                    continue

                product_attributes = getAttributesBySKU(product["PN"])
                if not product_attributes:
                    continue

                # Encontrar o preço correspondente
                price_info = df_precos[df_precos["SKU"] == product["PN"]]

                # Pular o produto se o PN não existir na lista de preços
                if len(price_info) == 0:
                    continue
                
                price_info = price_info.iloc[0].to_dict() if hasattr(price_info.iloc[0], 'to_dict') else dict(price_info.iloc[0])
                price_por = price_info.get("Preço Bundle R$", 0) / (1 - (20 / 100)) if price_info else None

                icms = price_info.get("ICMS %", 0)
                leadtime = 0
                if isinstance(icms, str):
                    icms = float(icms)

                if icms == 0.04 or icms == 0.18:
                    leadtime = "importado"
                elif icms == 0.07 or icms == 0.12:
                    leadtime = "local"

                produto_data = {
                    'name': str(product.get("SmartChoice", "")) + " " + str(product.get("Descrição", "")),
                    'sku': product["PN"],
                    'short_description': product.get("Descrição", ""),
                    'description': "HP " + product.get("Descrição", ""),
                    'price': str(price_por),
                    'regular_price': str(price_por),
                    'stock_quantity': 10,
                    'attributes': processar_attributes(product, price_info),
                    'meta_data': processar_fotos(product, images, normalized_family, product_info),
                    'dimensions': processar_dimensions(product, delivery, product_attributes),
                    'weight': str(processar_weight(product, delivery, product_attributes)),
                    'categories': processar_categories(product, "SmartChoice"),
                    'shipping_class': leadtime,
                    "manage_stock": True,
                }
                
            elif product.get("sheet_name") == "Portfólio Acessorios_Monitores":
                # Pular o produto se o SKU estiver vazio
                if "SKU" not in product or pd.isna(product["SKU"]):
                    continue

                product_info = getProductBySKU(product["SKU"])
                if not product_info:
                    continue

                product_attributes = getAttributesBySKU(product["SKU"])
                if not product_attributes:
                    continue

                # Encontrar o preço correspondente
                price_info = df_precos[df_precos["SKU"] == product["SKU"]]

                # Pular o produto se o SKU não existir na lista de preços
                if len(price_info) == 0:
                    continue
                
                price_info = price_info.iloc[0].to_dict() if hasattr(price_info.iloc[0], 'to_dict') else dict(price_info.iloc[0])
                price_por = price_info.get("Preço Bundle R$", 0) / (1 - (20 / 100)) if price_info else None

                pl_group = str(product.get("PL Description", "")).lower()
                categoria = "Display" if "display" in pl_group else "Acessório"

                icms = price_info.get("ICMS %", 0)
                
                leadtime = 0
                if isinstance(icms, str):
                    icms = float(icms)

                if icms == 0.04 or icms == 0.18:
                    leadtime = "importado"
                elif icms == 0.07 or icms == 0.12:
                    leadtime = "local"
                
                produto_data = {
                    'name': str(product.get("Descrição", "")),
                    'sku': product["SKU"],
                    'short_description': product.get("Descrição", ""),
                    'description': "HP " + product.get("Descrição", ""),
                    'price': str(price_por),
                    'regular_price': str(price_por),
                    'stock_quantity': 10,
                    'attributes': processar_attributes(product, price_info),
                    'meta_data': processar_fotos(product, images, normalized_family, product_info),
                    'dimensions': processar_dimensions(product, delivery, product_attributes),
                    'weight': str(processar_weight(product, delivery, product_attributes)),
                    'categories': processar_categories(product, categoria),
                    'shipping_class': leadtime,
                    "manage_stock": True,
                }
            
            else:
                # Pular o produto se o SKU estiver vazio
                if "SKU" not in product or pd.isna(product["SKU"]):
                    continue

                # Encontrar o preço correspondente
                price_info = df_precos[df_precos["SKU"] == product["SKU"]]

                # Pular o produto se o SKU não existir na lista de preços
                if len(price_info) == 0:
                    continue
                
                price_info = price_info.iloc[0].to_dict() if hasattr(price_info.iloc[0], 'to_dict') else dict(price_info.iloc[0])
                price_por = price_info.get("Preço Bundle R$", 0) / (1 - (20 / 100)) if price_info else None

                icms = price_info.get("ICMS %", 0)
                if isinstance(icms, str):
                    icms = float(icms)
                
                leadtime_map = {
                    0.04: "importado",
                    0.18: "importado",
                    0.07: "local",
                    0.12: "local"
                }
                leadtime = leadtime_map.get(icms, 0)
                
                product_info = getProductBySKU(product["SKU"])
                if not product_info:
                    continue

                product_attributes = getAttributesBySKU(product["SKU"])
                if not product_attributes:
                    continue

                # Converter o sheet_name usando o mapeamento
                with open('HP/maps/map.json', 'r') as f:
                    rename = json.load(f).get("TraducaoLinha", {})
                product_type = rename.get(product["sheet_name"], product["sheet_name"])

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
                    'description': "HP " + descricao,
                    'price': str(price_por),
                    'regular_price': str(price_por),
                    'stock_quantity': 10,
                    'attributes': processar_attributes(product, price_info),
                    'meta_data': processar_fotos(product, images, normalized_family, product_info),
                    'dimensions': processar_dimensions(product, delivery, product_attributes),
                    'weight': str(processar_weight(product, delivery, product_attributes)),
                    'categories': processar_categories(product, product_type),
                    'shipping_class': leadtime,
                    "manage_stock": True,
                }

            # Validar o produto antes de adicionar
            try:
                # Tentar converter o produto para JSON para validar
                json_str = json.dumps(produto_data, ensure_ascii=False)
                json.loads(json_str)  # Tentar carregar de volta para validar
                combined_data.append(produto_data)
                print(f"Produto {sku} processado com sucesso")
            except json.JSONDecodeError as e:
                print(f"ERRO: Produto {sku} com problema de JSON:")
                print(f"Erro: {str(e)}")
                print("Dados do produto:")
                for key, value in produto_data.items():
                    print(f"{key}: {type(value)} = {value}")
                raise  # Re-lança a exceção para interromper o processamento

        except Exception as e:
            print(f"\nERRO CRÍTICO ao processar produto {sku}:")
            print(f"Tipo do erro: {type(e).__name__}")
            print(f"Mensagem do erro: {str(e)}")
            print("Dados do produto original:")
            for key, value in product.items():
                print(f"{key}: {type(value)} = {value}")
            raise  # Re-lança a exceção para interromper o processamento
    
    # Converter os dados combinados para JSON e salvar na pasta
    try:
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'produtos_processados_hp.json')
        with open(output_path, 'w', encoding='utf-8') as json_file:
            json.dump(combined_data, json_file, ensure_ascii=False, indent=4)
        print("\nArquivo JSON salvo com sucesso!")
    except Exception as e:
        print(f"\nERRO ao salvar arquivo JSON:")
        print(f"Tipo do erro: {type(e).__name__}")
        print(f"Mensagem do erro: {str(e)}")
        raise
    
    #enviar_email(EmailProducts)
    return combined_data

def ler_arquivo_produto_hp(product_file):
    print("Iniciando leitura do arquivo de produtos...")
    try:
        contents = product_file.read()
        print("Arquivo lido com sucesso, convertendo para BytesIO...")
        product_excel = io.BytesIO(contents)
        
        # Obter todas as planilhas
        print("Lendo planilhas do Excel...")
        excel_sheets = pd.read_excel(product_excel, sheet_name=None)
        print(f"Planilhas encontradas: {list(excel_sheets.keys())}")
        
        # Remover primeira e última planilha
        sheet_names = list(excel_sheets.keys())[1:-1]
        print(f"Planilhas a serem processadas: {sheet_names}")
        
        all_products = []
        # Processar cada planilha separadamente
        for sheet_name in sheet_names:
            print(f"\nProcessando planilha: {sheet_name}")
            # Resetar o ponteiro do arquivo
            product_excel.seek(0)
            # Ler planilha com cabeçalho na segunda linha
            df = pd.read_excel(product_excel, sheet_name=sheet_name, header=1)
            print(f"Total de linhas na planilha {sheet_name}: {len(df)}")
            
            # Converter cada linha para um dicionário usando os cabeçalhos das colunas
            produtos_planilha = 0
            for _, row in df.iterrows():
                product_dict = {}
                product_dict['sheet_name'] = sheet_name  # Adicionar nome da planilha ao dicionário
                for column in df.columns:
                    if pd.notna(row[column]):  # Incluir apenas valores não nulos
                        product_dict[column] = row[column]
                if product_dict:  # Adicionar apenas se o dicionário não estiver vazio
                    all_products.append(product_dict)
                    produtos_planilha += 1
            
            print(f"Produtos processados na planilha {sheet_name}: {produtos_planilha}")
        
        print(f"\nTotal de produtos processados em todas as planilhas: {len(all_products)}")
        return all_products
    except Exception as e:
        print(f"\nERRO ao ler arquivo de produtos:")
        print(f"Tipo do erro: {type(e).__name__}")
        print(f"Mensagem do erro: {str(e)}")
        raise

def ler_arquivo_preco_hp(price_file):
    print("Iniciando leitura do arquivo de preços...")
    try:
        contents = price_file.read()
        print("Arquivo lido com sucesso, convertendo para BytesIO...")
        price_excel = io.BytesIO(contents)
        print("Lendo planilha SP do arquivo de preços...")
        price_df = pd.read_excel(price_excel, sheet_name="SP")
        print(f"Arquivo de preços lido com sucesso. Total de preços: {len(price_df)}")
        return price_df
    except Exception as e:
        print(f"\nERRO ao ler arquivo de preços:")
        print(f"Tipo do erro: {type(e).__name__}")
        print(f"Mensagem do erro: {str(e)}")
        raise

def processar_attributes(product, price_info):
    # Define coluna com um valor padrão
    coluna = "SKU"  # Valor padrão caso não seja nenhum dos casos específicos
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
            'options': str(anatel),
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
                'options': str(anatel),
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
                                'options': [str(valor)],
                                'visible': True
                            })

    #ean
    EAN = price_info.get("EAN", "")
    if EAN:
        attributes.append({
            'id': 13,
            'options': [EAN],
            'visible': True
        })

    attributes.append({
        'id': 46,
        'options': [family],
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

def processar_fotos(product, images, normalized_family, product_info):
    # Define coluna com um valor padrão
    coluna = "SKU"  # Valor padrão caso não seja nenhum dos casos específicos
    meta_data = []
    
    if not product_info or not isinstance(product_info, dict) or "data" not in product_info:
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
                pl_group = str(product.get("PL Description", "")).lower()
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
    else:
        try:
            devices = product_info.get("data", {}).get("devices", [])
            if devices and len(devices) > 0:
                device = devices[0]
                product_specs = device.get("productSpecs", {})
                if product_specs and "data" in product_specs:
                    image_uri = product_specs["data"].get("imageUri")
                    if image_uri:
                        meta_data.append({
                            "key": "_external_image_url",
                            "value": image_uri
                        })
        except Exception as e:
            print(f"Erro ao processar imagem do produto {product.get('SKU', 'SKU não encontrado')}: {str(e)}")
            # Se houver erro, tenta usar o método alternativo de busca de imagens
            return processar_fotos(product, images, normalized_family, None)
            
    return meta_data


def normalize_values_list(value):
    print(f"\nIniciando normalização de valores para: {value}")
    # Verifica se o valor já está no cache
    if value in normalized_values_cache:
        print(f"Valores de {value} encontrados no cache")
        return normalized_values_cache[value]
    
    print(f"Buscando valores de {value} na API...")
    normalize_values_list = {}
    
    # Valores padrão para fallback
    default_values = {
        "Familia": {
            "Notebook": "Notebook",
            "Desktop": "Desktop",
            "Workstation": "Workstation",
            "Thin Client": "Thin Client",
            "Display": "Display",
            "Acessório": "Acessório"
        },
        "Anatel": {
            "Notebook": "ANATEL: 12345",
            "Desktop": "ANATEL: 12346",
            "Workstation": "ANATEL: 12347",
            "Thin Client": "ANATEL: 12348",
            "Display": "ANATEL: 12349",
            "Acessório": "ANATEL: 12350"
        }
    }
    
    try:
        request = requests.get(f"https://eprodutos-integracao.microware.com.br/api/normalize-values")
        print(f"Status da resposta da API: {request.status_code}")
        
        if request.status_code == 200:
            print("Resposta recebida da API, tentando processar...")
            try:
                # Tenta processar a resposta em partes menores
                response_text = request.text
                
                # Encontra o início do objeto que contém os valores que queremos
                start_marker = f'"column":"{value}","from_to":'
                start_pos = response_text.find(start_marker)
                
                if start_pos != -1:
                    print(f"Encontrado início dos valores para {value}")
                    # Encontra o fim do objeto
                    start_pos += len(start_marker)
                    brace_count = 1
                    end_pos = start_pos
                    
                    while brace_count > 0 and end_pos < len(response_text):
                        if response_text[end_pos] == '{':
                            brace_count += 1
                        elif response_text[end_pos] == '}':
                            brace_count -= 1
                        end_pos += 1
                    
                    if brace_count == 0:
                        # Extrai apenas o objeto from_to
                        from_to_text = '{' + response_text[start_pos:end_pos-1]
                        try:
                            normalize_values_list = json.loads(from_to_text)
                            print(f"Valores extraídos com sucesso para {value}")
                        except json.JSONDecodeError as e:
                            print(f"Erro ao decodificar objeto from_to: {str(e)}")
                            print("Usando valores padrão como fallback")
                            normalize_values_list = default_values.get(value, {})
                    else:
                        print("Não foi possível encontrar o fim do objeto")
                        print("Usando valores padrão como fallback")
                        normalize_values_list = default_values.get(value, {})
                else:
                    print(f"Não foi possível encontrar os valores para {value}")
                    print("Usando valores padrão como fallback")
                    normalize_values_list = default_values.get(value, {})
                
                # Armazena no cache
                normalized_values_cache[value] = normalize_values_list
                print(f"Total de valores normalizados: {len(normalize_values_list)}")
                print("Valores armazenados no cache")
                
            except Exception as e:
                print(f"\nERRO ao processar resposta da API:")
                print(f"Tipo do erro: {type(e).__name__}")
                print(f"Mensagem do erro: {str(e)}")
                print("Usando valores padrão como fallback")
                normalize_values_list = default_values.get(value, {})
                normalized_values_cache[value] = normalize_values_list
        else:
            print(f"ERRO na API: Status {request.status_code}")
            print("Usando valores padrão como fallback")
            normalize_values_list = default_values.get(value, {})
            normalized_values_cache[value] = normalize_values_list
            
    except requests.exceptions.RequestException as e:
        print(f"\nERRO na requisição à API:")
        print(f"Tipo do erro: {type(e).__name__}")
        print(f"Mensagem do erro: {str(e)}")
        print("Usando valores padrão como fallback")
        normalize_values_list = default_values.get(value, {})
        normalized_values_cache[value] = normalize_values_list
    except Exception as e:
        print(f"\nERRO inesperado na normalização:")
        print(f"Tipo do erro: {type(e).__name__}")
        print(f"Mensagem do erro: {str(e)}")
        print("Usando valores padrão como fallback")
        normalize_values_list = default_values.get(value, {})
        normalized_values_cache[value] = normalize_values_list
        
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

def processar_dimensions(product, delivery_info, product_attributes):
    # Define coluna com um valor padrão
    coluna = "SKU"  # Valor padrão caso não seja nenhum dos casos específicos
    
    try:
        if not product_attributes:
            sheet_name = product.get("sheet_name", "")
            
            # Atualiza coluna baseado no tipo de produto
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
                dimensions = delivery_info_filtered.iloc[0]
                return {
                    "length": float(dimensions["depth"]),  
                    "width": float(dimensions["width"]),   
                    "height": float(dimensions["height"])  
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
            sku = product.get(coluna, "SKU não encontrado")
            EmailProducts.append(f"{sku} - Produto sem dimensoes")
            return {
                "length": 0.1,  # 10cm
                "width": 0.1,
                "height": 0.1
            }
        else:
            return process_dimensions(product_attributes)

    except Exception as e:
        print(f"Erro ao processar dimensões: {str(e)}")
        sku = product.get(coluna, "SKU não encontrado")
        EmailProducts.append(f"{sku} - Produto sem dimensoes")
        return {
            "length": 0.1,
            "width": 0.1,
            "height": 0.1
        }

def processar_weight(product, delivery_info, product_attributes):
    # Define coluna com um valor padrão
    coluna = "SKU"  # Valor padrão caso não seja nenhum dos casos específicos
    
    try:
        if not product_attributes:
            sheet_name = product.get("sheet_name", "")
            
            # Atualiza coluna baseado no tipo de produto
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
        else:
            return process_weight(product_attributes)

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


def getProductBySKU(sku):
    """Obtém informações do produto com cache"""
    sku = sku.split('#')[0] if '#' in sku else sku
    
    # Verifica cache primeiro
    cached_data = get_cached_data(sku, PRODUCT_CACHE_FILE)
    if cached_data:
        print(f"Usando cache para produto: {sku}")
        return cached_data
    
    # Se não estiver em cache, faz a chamada à API
    url = f"https://support.hp.com/wcc-services/profile/devices/warranty/specs?cache=true&authState=anonymous&template=ProductModel"
    headers = {
        'Content-Type': 'application/json',
        'Accept': '*/*',
        'User-Agent': 'insomnia/11.1.0'
    }
    body = {
        "cc": "br",
        "lc": "pt",
        "utcOffset": "M0300",
        "customerId": "",
        "deviceId": 1234,
        "devices": [
            {
                "seriesOid": None,
                "modelOid": None,
                "serialNumber": None,
                "productNumber": sku
            }
        ],
        "captchaToken": ""
    }
    try:
        response = requests.post(url, json=body, headers=headers, timeout=5)
        data = response.json()
        if not data or "data" not in data or "devices" not in data["data"] or not data["data"]["devices"]:
            return None
        device = data["data"]["devices"][0]
        if not device or "productSpecs" not in device or "data" not in device["productSpecs"]:
            return None
        
        # Salva no cache
        save_to_cache(sku, data, PRODUCT_CACHE_FILE)
        return data
    except Exception as e:
        print(f"Erro na API de produto: {str(e)}")
        return None

def process_dimensions(dimensions_data):
    if not dimensions_data or "data" not in dimensions_data or "products" not in dimensions_data["data"]:
        return {}
    
    # Pega o primeiro SKU da lista de produtos
    sku = list(dimensions_data["data"]["products"].keys())[0]
    product_dims = dimensions_data["data"]["products"][sku]
    
    # Lista de possíveis nomes de campos que podem conter dimensões
    dimension_fields = [
        "Dimensões com embalagem",
        "Package dimensions (W x D x H)",
        "Dimensões (L x P x A)",
        "Dimensions (W x D x H)",
        "Dimensões mínimas (L x P x A)",
        "Dimensões"  # mantém o campo original como fallback
    ]
    
    def clean_dimension_value(value):
        # Converte para minúsculo
        value = value.lower()
        
        # Remove textos comuns que podem aparecer
        remove_texts = [
            "system dimensions may fluctuate",
            "as dimensões do sistema podem ser diferentes",
            "due to configuration",
            "devido a configurações",
            "manufacturing variances",
            "variâncias na fabricação",
            "keyboard",
            "mouse",
            "teclado",
            "&lt;br /&gt;",
            "&gt;",
            "&lt;"
        ]
        
        for text in remove_texts:
            value = value.replace(text, "")
        
        # Remove parênteses e seu conteúdo
        value = re.sub(r'\([^)]*\)', '', value)
        
        # Remove texto após ponto e vírgula
        value = value.split(';')[0].strip()
        
        # Remove unidades e espaços extras
        value = value.replace("cm", "").replace("mm", "").replace("in", "").strip()
        
        # Substitui vírgula por ponto
        value = value.replace(",", ".")
        
        # Remove espaços extras
        value = " ".join(value.split())
        
        return value

    def convert_to_cm(value, original_value):
        try:
            # Se o valor original contém mm, converte para cm
            if "mm" in original_value.lower():
                return str(float(value) / 10)
            # Se o valor original contém in (polegadas), converte para cm
            elif "in" in original_value.lower():
                return str(float(value) * 2.54)
            return value
        except:
            return "0"

    def extract_dimensions(value):
        # Tenta encontrar padrões de dimensões (três números separados por x)
        pattern = r"(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*x\s*(\d+\.?\d*)"
        matches = re.findall(pattern, value)
        
        if matches:
            # Pega o primeiro conjunto de dimensões encontrado
            return matches[0]
        
        # Se não encontrou o padrão, tenta extrair números individuais
        numbers = re.findall(r"[-+]?\d*\.\d+|\d+", value)
        if len(numbers) >= 3:
            return (numbers[0], numbers[1], numbers[2])
        
        return None

    def process_single_dimension(value, original_value):
        try:
            value = clean_dimension_value(value)
            numbers = re.findall(r"[-+]?\d*\.\d+|\d+", value)
            if numbers:
                value = convert_to_cm(numbers[0], original_value)
                return {
                    "length": "0",
                    "width": value,
                    "height": "0"
                }
        except:
            pass
        return {}

    def process_three_dimensions(value, original_value):
        try:
            value = clean_dimension_value(value)
            dimensions = extract_dimensions(value)
            
            if dimensions:
                processed_dims = []
                for dim_value in dimensions:
                    dim_value = convert_to_cm(dim_value, original_value)
                    processed_dims.append(dim_value)
                
                return {
                    "length": processed_dims[0],
                    "width": processed_dims[1],
                    "height": processed_dims[2]
                }
        except:
            pass
        return {}

    # Procura por qualquer um dos campos de dimensões
    for dim in product_dims:
        if dim.get("name") in dimension_fields:
            try:
                original_value = dim.get("value", "").lower()
                if not original_value:
                    continue

                # Verifica se tem unidades de medida
                if not any(unit in original_value for unit in ["cm", "mm", "in"]):
                    continue

                # Tenta processar como três dimensões primeiro
                result = process_three_dimensions(original_value, original_value)
                if result:
                    return result

                # Se não conseguiu processar como três dimensões, tenta como dimensão única
                result = process_single_dimension(original_value, original_value)
                if result:
                    return result

            except Exception as e:
                print(f"Erro ao processar dimensões: {str(e)}")
                continue

    return {}

def process_weight(weight_data):
    if not weight_data or "data" not in weight_data or "products" not in weight_data["data"]:
        return ""
    
    # Pega o primeiro SKU da lista de produtos
    sku = list(weight_data["data"]["products"].keys())[0]
    product_weight = weight_data["data"]["products"][sku]

    # Lista de possíveis nomes de campos que podem conter peso
    weight_fields = [
        "Peso com embagem",
        "Package weight",
        "Peso",
        "Weight"
    ]

    def clean_weight_value(value):
        # Converte para minúsculo
        value = value.lower()
        
        # Remove textos comuns que podem aparecer
        remove_texts = [
            "with stand",
            "without stand",
            "starting at",
            "a partir de",
            "approximately",
            "approx",
            "aprox",
            "min",
            "max",
            "minimum",
            "maximum",
            "from",
            "de",
            "to",
            "até",
            "&lt;br /&gt;",
            "&gt;",
            "&lt;"
        ]
        
        for text in remove_texts:
            value = value.replace(text, "")
        
        # Remove parênteses e seu conteúdo
        value = re.sub(r'\([^)]*\)', '', value)
        
        # Remove texto após ponto e vírgula
        value = value.split(';')[0].strip()
        
        # Remove unidades e espaços extras
        value = value.replace("kg", "").replace("lb", "").strip()
        
        # Substitui vírgula por ponto
        value = value.replace(",", ".")
        
        # Remove espaços extras
        value = " ".join(value.split())
        
        return value

    def convert_to_kg(value, original_value):
        try:
            # Se o valor original contém lb, converte para kg
            if "lb" in original_value.lower():
                return str(float(value) * 0.45359237)
            return value
        except:
            return ""

    # Procura por qualquer um dos campos de peso
    for weight in product_weight:
        if weight.get("name") in weight_fields:
            try:
                original_value = weight.get("value", "").lower()
                if not original_value:
                    continue

                # Verifica se tem unidades de medida
                if not any(unit in original_value for unit in ["kg", "lb"]):
                    continue

                # Limpa o valor
                value = clean_weight_value(original_value)
                
                # Tenta extrair o primeiro número encontrado
                numbers = re.findall(r"[-+]?\d*\.\d+|\d+", value)
                if numbers:
                    value = numbers[0]
                    # Converte para kg se necessário
                    value = convert_to_kg(value, original_value)
                    return value

            except Exception as e:
                print(f"Erro ao processar peso: {str(e)}")
                continue

    return ""

def getAttributesBySKU(sku):
    """Obtém atributos do produto com cache"""
    sku = sku.split('#')[0] if '#' in sku else sku
    
    # Verifica cache primeiro
    cached_data = get_cached_data(sku, ATTRIBUTES_CACHE_FILE)
    if cached_data:
        print(f"Usando cache para atributos: {sku}")
        return cached_data
    
    # Se não estiver em cache, faz a chamada à API
    url = f"https://support.hp.com/wcc-services/pdp/specifications/br-pt?authState=anonymous&template=ProductModel&sku={sku}"
    headers = {
        'Content-Type': 'application/json',
        'Accept': '*/*',
        'User-Agent': 'insomnia/11.1.0'
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        
        # Salva no cache
        save_to_cache(sku, data, ATTRIBUTES_CACHE_FILE)
        return data
    except Exception as e:
        print(f"Erro na API de atributos: {str(e)}")
        return None