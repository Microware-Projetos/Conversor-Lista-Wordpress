import pandas as pd
import io
import sys
import os
import json
import requests
import re
import time
from datetime import datetime, timedelta

# Diretório para armazenar o cache
CACHE_DIR = "HP/cache"
PRODUCT_CACHE_FILE = os.path.join(CACHE_DIR, "product_cache.json")
ATTRIBUTES_CACHE_FILE = os.path.join(CACHE_DIR, "attributes_cache.json")
CACHE_EXPIRY_DAYS = 7  # Tempo em dias para expirar o cache

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

def processar_hp_dataAPI(produtos, precos):
    try:
        print("\nIniciando processamento dos dados...")
        print(f"Total de produtos recebidos: {len(produtos)}")
        print(f"Total de preços recebidos: {len(precos)}")
        
        # Converte os DataFrames para listas de dicionários
        produtos_list = produtos.to_dict('records')
        precos_list = precos.to_dict('records')
        
        print("\nProcessando produtos por tipo de sheet...")
        combined_data = combinar_dados(produtos_list, precos_list)
        print(f"\nTotal de produtos processados com sucesso: {len(combined_data)}")
        
        return combined_data
    except Exception as e:
        print(f"Mensagem do erro: {str(e)}")
        raise

def combinar_dados(df_produtos, df_precos):
    combined_data = []
    total_produtos = len(df_produtos)
    produtos_processados = 0
    produtos_pulados = 0
    
    print("\nIniciando combinação dos dados...")
    print(f"Total de produtos a processar: {total_produtos}")
    
    for index, product in enumerate(df_produtos, 1):
        try:
            # Identifica o tipo de produto pela sheet_name
            sheet_name = product.get("sheet_name", "")
            print(f"\nProcessando produto {index} de {total_produtos} (Sheet: {sheet_name})")
            
            # Verifica se tem identificador válido (PN ou SKU)
            if sheet_name == "SmartChoice":
                if "PN" not in product or pd.isna(product["PN"]):
                    print(f"Produto {index} pulado: PN não encontrado")
                    produtos_pulados += 1
                    continue
                sku = product["PN"]
            else:
                if "SKU" not in product or pd.isna(product["SKU"]):
                    print(f"Produto {index} pulado: SKU não encontrado")
                    produtos_pulados += 1
                    continue
                sku = product["SKU"]
            
            # Busca o preço correspondente
            price_info = next((p for p in df_precos if p["SKU"] == sku), None)
            if not price_info:
                print(f"Produto {index} pulado: Preço não encontrado para {sku}")
                produtos_pulados += 1
                continue
            
            # Processa o produto de acordo com o tipo
            try:
                if sheet_name == "SmartChoice":
                    produto_data = processar_smartchoice(product, price_info)
                elif sheet_name == "Portfólio Acessorios_Monitores":
                    produto_data = processar_portfolio(product, price_info)
                else:
                    produto_data = processar_outros(product, price_info)
                
                if produto_data:
                    combined_data.append(produto_data)
                    produtos_processados += 1
                    print(f"Produto {sku} processado com sucesso")
                else:
                    produtos_pulados += 1
                    print(f"Produto {sku} pulado: Erro no processamento específico")
                
            except Exception as e:
                produtos_pulados += 1
                print(f"Erro ao processar produto {sku}: {str(e)}")
                continue
            
            
        except Exception as e:
            produtos_pulados += 1
            print(f"Erro geral ao processar produto {index}: {str(e)}")
            continue
    
    print(f"\nResumo do processamento:")
    print(f"Total de produtos: {total_produtos}")
    print(f"Produtos processados com sucesso: {produtos_processados}")
    print(f"Produtos pulados: {produtos_pulados}")
    
    return combined_data

def processar_smartchoice(product, price_info):
    try:
        price_por = price_info["Preço Bundle R$"] / (1 - (20 / 100)) if price_info is not None else None
        icms = float(price_info["ICMS %"]) if isinstance(price_info["ICMS %"], str) else price_info["ICMS %"]
        leadtime_map = {
            0.04: "importado",
            0.18: "importado",
            0.07: "local",
            0.12: "local"
        }
        leadtime = leadtime_map.get(icms, 0)
        
        product_info = getProductBySKU(product["PN"])
        if not product_info:
            return None
            
        product_attributes = getAttributesBySKU(product["PN"])
        if not product_attributes:
            return None
            
        formatted_attributes = process_attributes(product_attributes)
        
        try:
            product_name = product_info["data"]["devices"][0]["productSpecs"]["data"].get("productName")
            if not product_name:
                product_name = product_info["data"]["devices"][0]["productSpecs"]["data"].get("productSeriesName")
            if not product_name:
                product_name = product.get("Descrição", "")
        except (KeyError, TypeError, IndexError):
            product_name = product.get("Descrição", "")
            
        return {
            'name': product_name,
            'sku': product["PN"],
            'short_description': product.get("Descrição", ""),
            'description': "HP " + product.get("Descrição", ""),
            'price': price_por,
            'regular_price': price_por,
            'stock_quantity': 10,
            'attributes': formatted_attributes,
            'meta_data': processar_fotos(product_info),
            'dimensions': process_dimensions(product_attributes),
            'weight': process_weight(product_attributes),
            'categories': processar_categories(product, "SmartChoice"),
            'shipping_class': leadtime,
            "manage_stock": True,
        }
    except Exception as e:
        print(f"Erro ao processar SmartChoice: {str(e)}")
        return None

def processar_portfolio(product, price_info):
    try:
        price_por = price_info["Preço Bundle R$"] / (1 - (20 / 100)) if price_info is not None else None
        icms = float(price_info["ICMS %"]) if isinstance(price_info["ICMS %"], str) else price_info["ICMS %"]
        leadtime_map = {
            0.04: "importado",
            0.18: "importado",
            0.07: "local",
            0.12: "local"
        }
        leadtime = leadtime_map.get(icms, 0)
        
        product_info = getProductBySKU(product["SKU"])
        if not product_info:
            return None
            
        product_attributes = getAttributesBySKU(product["SKU"])
        if not product_attributes:
            return None
            
        formatted_attributes = process_attributes(product_attributes)
        
        pl_group = str(product.get("PL GROUP", "")).lower()
        categoria = "Display" if "display" in pl_group else "Acessório"
        
        try:
            product_name = product_info["data"]["devices"][0]["productSpecs"]["data"].get("productSeriesName")
            if not product_name:
                product_name = product_info["data"]["devices"][0]["productSpecs"]["data"].get("productName")
            if not product_name:
                product_name = product.get("DESCRIÇÃO", "")                
        except (KeyError, TypeError, IndexError):
            product_name = product.get("DESCRIÇÃO", "")
            
        return {
            'name': product_name,
            'sku': product["SKU"],
            'short_description': product.get("DESCRIÇÃO", ""),
            'description': "HP " + product.get("DESCRIÇÃO", ""),
            'price': price_por,
            'regular_price': price_por,
            'stock_quantity': 10,
            'attributes': formatted_attributes,
            'meta_data': processar_fotos(product_info),
            'dimensions': process_dimensions(product_attributes),
            'weight': process_weight(product_attributes),
            'categories': processar_categories(product, categoria),
            'shipping_class': leadtime,
            "manage_stock": True,
        }
    except Exception as e:
        print(f"Erro ao processar Portfólio: {str(e)}")
        return None

def processar_outros(product, price_info):
    try:
        price_por = price_info["Preço Bundle R$"] / (1 - (20 / 100)) if price_info is not None else None
        icms = float(price_info["ICMS %"]) if isinstance(price_info["ICMS %"], str) else price_info["ICMS %"]
        leadtime_map = {
            0.04: "importado",
            0.18: "importado",
            0.07: "local",
            0.12: "local"
        }
        leadtime = leadtime_map.get(icms, 0)
        
        product_info = getProductBySKU(product["SKU"])
        if not product_info:
            return None
            
        product_attributes = getAttributesBySKU(product["SKU"])
        if not product_attributes:
            return None
            
        formatted_attributes = process_attributes(product_attributes)
        
        with open('HP/maps/map.json', 'r') as f:
            rename = json.load(f).get("TraducaoLinha", {})
        
        # Garante que sheet_name seja uma string
        sheet_name = str(product.get("sheet_name", ""))
        print(f"Sheet name: {sheet_name} (tipo: {type(sheet_name)})")
        
        # Garante que product_type seja uma string
        product_type = str(rename.get(sheet_name, sheet_name))
        print(f"Product type: {product_type} (tipo: {type(product_type)})")
        
        try:
            product_name = product_info["data"]["devices"][0]["productSpecs"]["data"].get("productSeriesName")
            if not product_name:
                product_name = product_info["data"]["devices"][0]["productSpecs"]["data"].get("productName")
            if not product_name:
                product_name = str(product.get("DESCRIÇÃO", ""))                
        except (KeyError, TypeError, IndexError):
            product_name = str(product.get("DESCRIÇÃO", ""))
            
        # Converte o Model para string e remove caracteres especiais
        descricao = product_type + " " + str(product.get("Model", "")) + " " + str(product.get("Processor", "")) + " " + str(product.get("OS", "")) + " " + str(product.get("Memory", ""))

        if product_type == "Notebook":
            descricao += " " + str(product.get("Internal Storage", ""))
        elif product_type == "Desktop":
            descricao += " " + str(product.get("Internal Storage 1", ""))
        elif product_type == "Mobile":
            descricao += " " + str(product.get("Primary Storage Drive", ""))
        elif product_type == "Workstation":
            descricao += " " + str(product.get("Storage - Hard Drive 1", ""))
        elif product_type == "Thin Client":
            descricao += " " + str(product.get("Processador", "")) + " " + str(product.get("RAM (MB)", "")) + " " + str(product.get("FLASH (GF)", ""))
            
        return {
            'name': product_name,
            'sku': product["SKU"],
            'short_description': descricao,
            'description': f"HP {descricao}",
            'price': price_por,
            'regular_price': price_por,
            'stock_quantity': 10,
            'attributes': formatted_attributes,
            'meta_data': processar_fotos(product_info),
            'dimensions': process_dimensions(product_attributes),
            'weight': process_weight(product_attributes),
            'categories': processar_categories(product, product_type),
            'shipping_class': leadtime,
            "manage_stock": True,
        }
    except Exception as e:
        print(f"Erro ao processar Outros: {str(e)}")
        print(f"Detalhes do erro: {type(e).__name__}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return None

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

def process_attributes(attributes_data):
    if not attributes_data or "data" not in attributes_data or "products" not in attributes_data["data"]:
        return []
    
    formatted_attributes = []
    # Pega o primeiro SKU da lista de produtos
    sku = list(attributes_data["data"]["products"].keys())[0]
    product_attrs = attributes_data["data"]["products"][sku]
    
    # Processa todos os atributos que têm nome e valor
    for attr in product_attrs:
        if attr.get("name") and attr.get("value") and attr["containerFormatCode"] in ["ST", "LS"]:
            # Remove notas de rodapé e outros textos entre colchetes
            value = re.sub(r'\[.*?\]', '', attr["value"]).strip()
            if value:  # Só adiciona se ainda houver valor após a limpeza
                formatted_attributes.append({
                    "name": attr["name"],
                    "value": value,
                    "visible": True,
                    "variation": False
                })
    
    return formatted_attributes

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

def processar_fotos(product_info):
    if not product_info or "data" not in product_info or "devices" not in product_info["data"]:
        return []
        
    try:
        image_uri = product_info["data"]["devices"][0]["productSpecs"]["data"].get("imageUri")
        if image_uri:
            return [{
                "key": "_external_image_url",
                "value": image_uri
            }]
    except (KeyError, TypeError, IndexError) as e:
        print(f"Erro ao processar foto do produto: {str(e)}")
    
    return []

# Inicializa o diretório de cache quando o módulo é carregado
ensure_cache_dir()