from . import microware_bp
from flask import jsonify, render_template, request, Response
from .processors import processar_microware_data
import pandas as pd
import json
import asyncio
import aiohttp
import time

WOOCOMMERCE_CONSUMER_KEY = 'ck_61a4553a27abc85ae9ae20071fcdc82364906796'
WOOCOMMERCE_CONSUMER_SECRET = 'cs_76a1d25d7d9db8a665106e458727b3079f7ba67d'

# Variável global para armazenar o progresso
progresso_atual = {
    'loteAtual': 0,
    'total': 0,
    'status': 'Aguardando...',
    'erros': 0,
    'sucessos': 0
}

import aiohttp

import aiohttp

import aiohttp

async def deletar_todos_produtos():
    url_base = "https://ecommerce.microware.com.br/marketplace/wp-json/wc/v3/products"
    batch_url = f"{url_base}/batch"
    auth = aiohttp.BasicAuth(WOOCOMMERCE_CONSUMER_KEY, WOOCOMMERCE_CONSUMER_SECRET)

    async with aiohttp.ClientSession() as session:
        page = 1
        while True:
            # Busca produtos da página atual
            async with session.get(
                url_base,
                auth=auth,
                params={"per_page": 100, "page": page}
            ) as response:
                produtos = await response.json()

                if not produtos:
                    break

                ids_para_deletar = [produto["id"] for produto in produtos]

                # Envia requisição POST (não DELETE)
                async with session.post(
                    batch_url,
                    auth=auth,
                    params={"force": "true"},
                    json={"delete": ids_para_deletar}
                ) as delete_response:
                    if delete_response.status == 200:
                        print(f"Batch da página {page} deletado com sucesso.")
                    else:
                        print(f"Erro ao deletar batch da página {page}: {delete_response.status}")
                        print(await delete_response.text())

                page += 1

    print("Todos os produtos foram deletados com sucesso (em batch)!")




@microware_bp.route('/progresso')
def progresso():
    def gerar_eventos():
        while True:
            yield f"data: {json.dumps(progresso_atual)}\n\n"
            time.sleep(1)
    
    return Response(gerar_eventos(), mimetype='text/event-stream')

@microware_bp.route('/microware', methods=['GET'])
def listar_produtos():
    return render_template('microware_upload.html')

@microware_bp.route('/microware', methods=['POST'])
async def processar_arquivo():
    global progresso_atual
    arquivo = request.files.get('arquivo')
    if not arquivo:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400

    try:
        # Lê o arquivo Excel e converte para um dicionário de DataFrames
        microware_data = {'Sheet1': pd.read_excel(arquivo, sheet_name=0, header=1)}
        
        # Imprime os cabeçalhos do DataFrame
        print("\nCabeçalhos do arquivo Excel:")
        print(microware_data['Sheet1'].columns.tolist())
        
        produtos_processados = processar_microware_data(microware_data)
        
        # Cria um JSON e salva na pasta
        with open('produtos_processados_mw.json', 'w') as json_file:
            json.dump(produtos_processados, json_file, ensure_ascii=False, indent=4)

        # Deleta todos os produtos existentes antes de enviar os novos
        progresso_atual['status'] = 'Deletando produtos existentes...'
        await deletar_todos_produtos()

        url = "https://ecommerce.microware.com.br/marketplace/wp-json/wc/v3/products/batch?force=true"

        total_produtos = len(produtos_processados)
        print(f"Iniciando envio de {total_produtos} produtos em batch...")
        progresso_atual['total'] = (total_produtos + 9) // 10
        progresso_atual['erros'] = 0
        progresso_atual['sucessos'] = 0

        batch_payload = {
            "create": produtos_processados
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                auth=aiohttp.BasicAuth(WOOCOMMERCE_CONSUMER_KEY, WOOCOMMERCE_CONSUMER_SECRET),
                json=batch_payload,
            ) as response:
                response_data = await response.json()
                print("\nProcesso de envio concluído!")
                progresso_atual['status'] = 'Processo de envio concluído!'
                return jsonify({
                    'mensagem': 'Processo de envio concluído!',
                    'dados': produtos_processados
                })

    except Exception as erro_geral:
        print(f"Erro geral no processamento: {str(erro_geral)}")
        with open('erro_geral_envio.txt', 'w') as f:
            f.write(str(erro_geral))
        progresso_atual['status'] = 'Erro!'
        return jsonify({'erro': str(erro_geral)})
