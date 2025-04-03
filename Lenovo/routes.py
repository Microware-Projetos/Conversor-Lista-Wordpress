from . import lenovo_bp
from flask import jsonify, render_template, request
import pandas as pd
import json

@lenovo_bp.route('/lenovo', methods=['GET'])
def listar_produtos():
    return render_template('lenovo_upload.html')

@lenovo_bp.route('/lenovo', methods=['POST'])
def processar_arquivo():
    arquivo = request.files.get('arquivo')
    if not arquivo:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400

    lenovo_data = pd.read_excel(arquivo, sheet_name=None)

    try:
        processar_lenovo_data(lenovo_data)
          # Gera um arquivo JSON com os dados processados
        produtos_processados = processar_lenovo_data(lenovo_data)
        with open('produtos_processados.json', 'w') as json_file:
            json.dump(produtos_processados, json_file, ensure_ascii=False, indent=4)
    except Exception as e:
        return jsonify({'erro': f'Erro ao processar o arquivo: {str(e)}'}), 500

    return jsonify({'mensagem': 'Arquivo Excel manipulado com sucesso'})


def processar_lenovo_data(lenovo_data):
    # Converte o dicionário de DataFrames em um único DataFrame
    products_df = pd.concat(lenovo_data.values(), ignore_index=True)
    
    # Filtra os produtos
    products_df = products_df[
        (products_df["STATE"].str.lower().str.strip() == "sp") &
        (products_df["CUSTOMER_TYPE"].str.lower().str.strip() == "revenda sem regime")
    ]
    MANUFACTURE = "Lenovo"
    STOCK = 10
    MARGIN = 20 

    combined_data = []
    for _, product in products_df.iterrows():
        combined_data.append({
            'name': product['PRODUCT_DESCRIPTION'],
            'sku': product['PRODUCT_CODE'],
            'short_description': product['PH4_DESCRIPTION'],
            'price': product['UNIT_GROSS_PRICE(R$)'] * (1 + MARGIN / 100),
            'stock_quantity': 100,
            'attributes': processar_attributes(product)
        })
    return combined_data

def processar_attributes(product):
    attributes = []
    with open('maps/attributesLenovo.json', 'r') as f:
        attributes_mapping = json.load(f)[0] 

    with open('maps/attributesWordpress.json', 'r') as f:
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
                        'options': [valor]
                    })
                print(f"Atributo processado: {wp_name} (ID: {wp_attribute['id']}) = {valor}")
       
    return attributes
    
    