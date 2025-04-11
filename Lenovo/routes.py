from . import lenovo_bp
from flask import jsonify, render_template, request
import pandas as pd
import json
import requests
from requests.auth import HTTPBasicAuth
import time
from .processors import processar_lenovo_data

# Configurações da API WooCommerce
WOOCOMMERCE_CONSUMER_KEY = 'ck_d1082fbea981c4912e59da8820c1cebea16d6923'
WOOCOMMERCE_CONSUMER_SECRET = 'cs_8949a97be104dd97aa02ae6d3b363325ed139765'

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
       
        # Processa os dados da Lenovo
        produtos_processados = processar_lenovo_data(lenovo_data)
        
        # Cria um JSON e salva na pasta
        with open('produtos_processados.json', 'w') as json_file:
            json.dump(produtos_processados, json_file, ensure_ascii=False, indent=4)
        
        
        url = "https://ecommerce-teste.microware.com.br/lenovo/wp-json/wc/v3/products/batch"
        
        total_produtos = len(produtos_processados)
        print(f"Iniciando envio de {total_produtos} produtos em batch...")
        
        # Processa apenas o primeiro lote de 10 produtos para teste
        lote_atual = produtos_processados[0:10]
        print(f"\nEnviando lote de produtos 1 até {min(10, total_produtos)} de {total_produtos}")
        
        # Prepara o payload do batch
        batch_payload = {
            "create": lote_atual
        }
        
        result = requests.post(
            url, 
            auth=HTTPBasicAuth(WOOCOMMERCE_CONSUMER_KEY, WOOCOMMERCE_CONSUMER_SECRET), 
            json=batch_payload
        )
        
        print(f"Status do envio do lote: {result.status_code}")
        if result.status_code != 200:
            print(f"Resposta da API: {result.text}")
        
        # Processa os produtos em lotes de 10
        for i in range(0, total_produtos, 10):
            lote_atual = produtos_processados[i:i+10]
            print(f"\nEnviando lote de produtos {i+1} até {min(i+10, total_produtos)} de {total_produtos}")
            
            # Prepara o payload do batch
            batch_payload = {
                "create": lote_atual
            }
            
            result = requests.post(
                url, 
                auth=HTTPBasicAuth(WOOCOMMERCE_CONSUMER_KEY, WOOCOMMERCE_CONSUMER_SECRET), 
                json=batch_payload
            )
            
            print(f"Status do envio do lote: {result.status_code}")
            if result.status_code != 200:
                print(f"Resposta da API: {result.text}")
            
            print(f"Lote {i//10 + 1} concluído!")
            time.sleep(1)  # Pausa entre os lotes

        print("\nProcesso de envio concluído!")

    except Exception as e:
        return jsonify({'erro': f'Erro ao processar o arquivo: {str(e)}'}), 500

    return jsonify({'mensagem': 'Lista enviada com sucesso'})