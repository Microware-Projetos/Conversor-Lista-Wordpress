from . import hp_bp
from flask import jsonify, render_template, request, Response
import pandas as pd
import json
import aiohttp
import asyncio
from requests.auth import HTTPBasicAuth
import time
from .processors import processar_hp_data
from collections import deque

# Configurações da API WooCommerce
WOOCOMMERCE_CONSUMER_KEY = 'ck_131b451fd7b97ebbb0dfaab74ebd5ce3868e50fe'
WOOCOMMERCE_CONSUMER_SECRET = 'cs_2fd8a064e9f6df929a2d63c7eceb26dea344b517'

# Variável global para armazenar o progresso
progresso_atual = {
    'loteAtual': 0,
    'total': 0,
    'status': 'Aguardando...',
    'erros': 0,
    'sucessos': 0
}

async def enviar_lote(session, lote, numero_lote, url, max_tentativas=5):
    batch_payload = {
        "create": lote
    }
    
    tentativas = 0
    while tentativas < max_tentativas:
        try:
            # Validação dos produtos
            for produto in lote:
                if not all([produto.get('name'), produto.get('sku'), produto.get('price')]):
                    raise Exception(f"Produto inválido no lote {numero_lote}: {produto}")

            async with session.post(
                url,
                auth=aiohttp.BasicAuth(WOOCOMMERCE_CONSUMER_KEY, WOOCOMMERCE_CONSUMER_SECRET),
                json=batch_payload,
                timeout=300  # 5 minutos
            ) as response:
                if response.status == 200:
                    print(f"Lote {numero_lote} enviado com sucesso!")
                    progresso_atual['sucessos'] += 1
                    return True
                else:
                    raise Exception(f"Erro API: {response.status} - {await response.text()}")

        except Exception as e:
            tentativas += 1
            print(f"Tentativa {tentativas} falhou para o lote {numero_lote}: {str(e)}")
            progresso_atual['erros'] += 1
            
            with open(f'erro_lote_{numero_lote}_tentativa_{tentativas}.txt', 'w') as f:
                f.write(str(e))
            
            if tentativas == max_tentativas:
                print(f"Erro crítico: lote {numero_lote} falhou após {max_tentativas} tentativas.")
                return False
            
            # Espera progressiva entre tentativas (2, 4, 8, 16, 32 segundos)
            await asyncio.sleep(2 ** tentativas)
    
    return False

@hp_bp.route('/progresso')
def progresso():
    def gerar_eventos():
        while True:
            yield f"data: {json.dumps(progresso_atual)}\n\n"
            time.sleep(1)
    
    return Response(gerar_eventos(), mimetype='text/event-stream')

@hp_bp.route('/hp', methods=['GET'])
def listar_produtos():
    return render_template('hp_upload.html')

@hp_bp.route('/hp', methods=['POST'])
async def processar_arquivo():
    global progresso_atual
    arquivo_produtos = request.files.get('arquivo_produtos')
    arquivo_precos = request.files.get('arquivo_precos')
    
    if not arquivo_produtos or not arquivo_precos:
        return jsonify({'erro': 'Por favor, envie ambos os arquivos (produtos e preços)'}), 400

    try:
        produtos_processados = processar_hp_data(arquivo_produtos, arquivo_precos)
        
        # Cria um JSON e salva na pasta
        with open('produtos_processados.json', 'w') as json_file:
            json.dump(produtos_processados, json_file, ensure_ascii=False, indent=4)
        
        return jsonify({
            'mensagem': 'Produtos processados com sucesso.',
            'total_produtos': len(produtos_processados)
        })

    except Exception as erro_geral:
        erro_msg = str(erro_geral) if erro_geral else "Erro desconhecido ao processar arquivos"
        print(f"Erro geral no envio: {erro_msg}")
        with open('erro_geral_envio.txt', 'w') as f:
            f.write(erro_msg)
        progresso_atual['status'] = 'Erro!'
        return jsonify({'erro': erro_msg}), 500