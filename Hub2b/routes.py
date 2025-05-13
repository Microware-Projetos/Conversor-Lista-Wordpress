from . import hub2b_bp
from flask import jsonify, render_template, request, Response
import pandas as pd
import json
import asyncio
import aiohttp
import time
import os
from datetime import datetime
from .processor import buscar_produtos, processar_produtos, enviar_produtos
import pytz

WOOCOMMERCE_CONSUMER_KEY_Lenovo = 'ck_27e249ea7ce48002377a8b34e210d56e683ba8a7'
WOOCOMMERCE_CONSUMER_SECRET_Lenovo = 'cs_326d654a9c568295e92714d51e93a4605e2683bf'

WOOCOMMERCE_CONSUMER_KEY_HP = 'ck_131b451fd7b97ebbb0dfaab74ebd5ce3868e50fe'
WOOCOMMERCE_CONSUMER_SECRET_HP = 'cs_2fd8a064e9f6df929a2d63c7eceb26dea344b517'

HISTORICO_FILE = 'historico_envios.json'

def salvar_historico(marca, status):
    historico = []
    try:
        if os.path.exists(HISTORICO_FILE) and os.path.getsize(HISTORICO_FILE) > 0:
            with open(HISTORICO_FILE, 'r') as f:
                try:
                    historico = json.load(f)
                except json.JSONDecodeError:
                    historico = []
    except Exception as e:
        print(f"Erro ao ler histórico: {str(e)}")
        historico = []
    
    # Definir o timezone de São Paulo
    sp_timezone = pytz.timezone('America/Sao_Paulo')
    data_atual = datetime.now(sp_timezone)
    
    historico.append({
        'marca': marca,
        'data': data_atual.isoformat(),
        'status': status
    })
    
    try:
        with open(HISTORICO_FILE, 'w') as f:
            json.dump(historico, f, indent=4)
    except Exception as e:
        print(f"Erro ao salvar histórico: {str(e)}")

@hub2b_bp.route('/hub2b', methods=['GET'])
def listar_produtos():
    return render_template('hub2b.html')

@hub2b_bp.route('/hub2b/enviar', methods=['POST'])
async def enviar_produtos_rota():
    try:
        print("Iniciando processo de envio...")
        data = request.get_json()
        marca = data.get('marca')
        print(f"Marca selecionada: {marca}")
        
        consumer_key = None
        consumer_secret = None
         
        if marca == 'Lenovo':
            consumer_key = WOOCOMMERCE_CONSUMER_KEY_Lenovo
            consumer_secret = WOOCOMMERCE_CONSUMER_SECRET_Lenovo
        elif marca == 'HP':
            consumer_key = WOOCOMMERCE_CONSUMER_KEY_HP
            consumer_secret = WOOCOMMERCE_CONSUMER_SECRET_HP
        else:
            print(f"Marca inválida: {marca}")
            return jsonify({'success': False, 'message': 'Marca inválida'})
        
        print("Buscando produtos do WooCommerce...")
        # Busca os produtos do WooCommerce
        produtos = await buscar_produtos(marca, consumer_key, consumer_secret)
        print(f"Produtos encontrados: {len(produtos)}")
        
        print("Processando produtos para o Hub2b...")
        # Processa os produtos para o Hub2b
        produtos_processados = processar_produtos(produtos, marca)
        print(f"Produtos processados: {len(produtos_processados)}")
        
        print("Enviando produtos para o Hub2b...")
        # Envia os produtos para o Hub2b
        resultados = await enviar_produtos(produtos_processados)
        print("Envio concluído!")

        salvar_historico(marca, 'Enviado com sucesso')
        return jsonify({'success': True, 'message': f'Enviados {len(produtos)} produtos com sucesso!'})
        
    except Exception as e:
        print(f"Erro durante o processo de envio: {str(e)}")
        import traceback
        print(f"Traceback completo: {traceback.format_exc()}")
        salvar_historico(marca, f'Erro: {str(e)}')
        return jsonify({'success': False, 'message': str(e)})

@hub2b_bp.route('/hub2b/historico', methods=['GET'])
def obter_historico():
    try:
        if os.path.exists(HISTORICO_FILE):
            with open(HISTORICO_FILE, 'r') as f:
                historico = json.load(f)
            return jsonify(historico)
        return jsonify([])
    except Exception as e:
        return jsonify([])









