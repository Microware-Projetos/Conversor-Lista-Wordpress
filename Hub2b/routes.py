from . import hub2b_bp
from flask import jsonify, render_template, request, Response, send_file
import pandas as pd
import json
import asyncio
import aiohttp
import time
import os
from datetime import datetime
from .processor import buscar_produtos, processar_produtos, enviar_produtos, gerar_panilha_hub2b
import pytz
import io

WOOCOMMERCE_CONSUMER_KEY_Lenovo = 'ck_27e249ea7ce48002377a8b34e210d56e683ba8a7'
WOOCOMMERCE_CONSUMER_SECRET_Lenovo = 'cs_326d654a9c568295e92714d51e93a4605e2683bf'

WOOCOMMERCE_CONSUMER_KEY_HP = 'ck_131b451fd7b97ebbb0dfaab74ebd5ce3868e50fe'
WOOCOMMERCE_CONSUMER_SECRET_HP = 'cs_2fd8a064e9f6df929a2d63c7eceb26dea344b517'

HISTORICO_FILE = 'historico_envios.json'

def salvar_historico(marca, status, total_produtos=None, total_sucessos=None):
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
        'status': status,
        'total_produtos': total_produtos,
        'total_sucessos': total_sucessos
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
        total_produtos = len(produtos)
        print(f"Produtos encontrados: {total_produtos}")
        
        print("Processando produtos para o Hub2b...")
        # Processa os produtos para o Hub2b
        produtos_processados = processar_produtos(produtos, marca)
        print(f"Produtos processados: {len(produtos_processados)}")
        
        print("Enviando produtos para o Hub2b...")
        # Envia os produtos para o Hub2b
        resultados = await enviar_produtos(produtos_processados)
        total_sucessos = sum(1 for r in resultados if r == 'sucesso')
        print("Envio concluído!")

        # Salvar histórico com os resultados do envio
        salvar_historico(marca, 'Enviado com sucesso', total_produtos, total_sucessos)
        return jsonify({'success': True, 'message': f'Enviados {total_sucessos} de {total_produtos} produtos com sucesso!'})
        
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

@hub2b_bp.route('/hub2b/gerar-planilha', methods=['POST'])
async def gerar_planilha_rota():
    try:
        print("Iniciando geração da planilha...")
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
        
        print("Gerando planilha...")
        # Gera a planilha
        dados_planilha = gerar_panilha_hub2b(produtos, marca)
        
        # Cria um DataFrame do pandas
        df = pd.DataFrame(dados_planilha)
        
        # Cria um buffer de memória para o arquivo Excel
        output = io.BytesIO()
        
        # Salva o DataFrame como Excel no buffer usando apenas pandas
        df.to_excel(output, index=False, sheet_name='Produtos')
        
        # Move o cursor para o início do buffer
        output.seek(0)
        
        # Gera o nome do arquivo com a data atual
        data_atual = datetime.now().strftime('%Y%m%d_%H%M%S')
        nome_arquivo = f'produtos_hub2b_{marca}_{data_atual}.xlsx'
        
        print("Planilha gerada com sucesso!")
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=nome_arquivo
        )
        
    except Exception as e:
        print(f"Erro durante a geração da planilha: {str(e)}")
        import traceback
        print(f"Traceback completo: {traceback.format_exc()}")
        return jsonify({'success': False, 'message': str(e)})









