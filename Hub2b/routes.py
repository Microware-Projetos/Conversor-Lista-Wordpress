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
    
    historico.append({
        'marca': marca,
        'data': datetime.now().isoformat(),
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
async def enviar_produtos():
    try:
        data = request.get_json()
        marca = data.get('marca')
        consumer_key = None
        consumer_secret = None
         
        if marca == 'Lenovo':
            consumer_key = WOOCOMMERCE_CONSUMER_KEY_Lenovo
            consumer_secret = WOOCOMMERCE_CONSUMER_SECRET_Lenovo
        elif marca == 'HP':
            consumer_key = WOOCOMMERCE_CONSUMER_KEY_HP
            consumer_secret = WOOCOMMERCE_CONSUMER_SECRET_HP
        else:
            return jsonify({'success': False, 'message': 'Marca inválida'})
        
        # Busca os produtos do WooCommerce
        produtos = await buscar_produtos(marca, consumer_key, consumer_secret)
        produtos_processados = processar_produtos(produtos, marca)
        
        # Json de produtos processados
        with open('produtos_hub2b_processados.json', 'w') as f:
            json.dump(produtos_processados, f, indent=4)

        print(f"Total de produtos encontrados para {marca}: {len(produtos)}")
        salvar_historico(marca, 'Enviado com sucesso')
        return jsonify({'success': True})
        
    except Exception as e:
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









