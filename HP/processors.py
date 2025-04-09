import pandas as pd
import io
import sys
import os
import json

def processar_hp_data(produtos, precos):
    df_produtos = ler_arquivo_produto_hp(produtos)
    df_precos = ler_arquivo_preco_hp(precos)

    combined_data = combinar_dados(df_produtos, df_precos)
    
    return combined_data

def combinar_dados(df_produtos, df_precos):
    combined_data = []
    
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
                'regular_price': price_por,
                'stock_quantity': 100,
                'attributes': processar_attributes(product),
                'images': processar_fotos(),
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
            categoria = "Monitor" if "display" in pl_group else "Acessório"

            produto_data = {
                'name': str(product.get("SmartChoice", "")) + " " + str(product.get("Descrição", "")),
                'sku': product["SKU"],
                'short_description': product.get("Descrição", ""),
                'regular_price': price_por,
                'stock_quantity': 100,
                'attributes': processar_attributes(product),
                'images': processar_fotos(),
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
                'name': product["Model"],
                'sku': product["SKU"],
                'short_description': descricao,
                'regular_price': price_por,
                'stock_quantity': 100,
                'attributes': processar_attributes(product),
                'images': processar_fotos(),
            }
            combined_data.append(produto_data)
    
    # Converter os dados combinados para JSON e salvar na pasta
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'produtos_processados_hp.json')
    with open(output_path, 'w', encoding='utf-8') as json_file:
        json.dump(combined_data, json_file, ensure_ascii=False, indent=4)
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
                    
    return attributes

def processar_fotos():   
    return []

