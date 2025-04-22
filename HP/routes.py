from . import hp_bp
from flask import jsonify, render_template, request, Response
import pandas as pd
import json
from .processors import processar_hp_data
import requests
from requests.auth import HTTPBasicAuth 
import time
# Configurações da API WooCommerce
WOOCOMMERCE_CONSUMER_KEY = 'ck_420e820fb1bbf2948d4eddce62e8496cf87669bb'
WOOCOMMERCE_CONSUMER_SECRET = 'cs_7d6b623f7769a9183a32c8a102e2378c79e14d3b'

# Variável global para armazenar o progresso
progresso_atual = {
    'loteAtual': 0,
    'total': 0,
    'status': 'Aguardando...'
}

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
def processar_arquivo():
    global progresso_atual
    arquivo_produtos = request.files.get('arquivo_produtos')
    arquivo_precos = request.files.get('arquivo_precos')
    
    if not arquivo_produtos or not arquivo_precos:
        return jsonify({'erro': 'Por favor, envie ambos os arquivos (produtos e preços)'}), 400

    try:
        produtos_processados = processar_hp_data(arquivo_produtos, arquivo_precos)

        url = "https://ecommerce-teste.microware.com.br/hp/wp-json/wc/v3/products/batch"
        total_produtos = len(produtos_processados)
        print(f"Iniciando envio de {total_produtos} produtos em batch...")

        progresso_atual['total'] = (total_produtos + 9) // 10

        for i in range(0, total_produtos, 10):
            lote_atual = produtos_processados[i:i + 10]
            numero_lote = (i // 10) + 1
            print(f"\nEnviando lote {numero_lote} ({i + 1} até {min(i + 10, total_produtos)} de {total_produtos})")

            progresso_atual['loteAtual'] = numero_lote
            progresso_atual['status'] = f'Enviando lote {numero_lote} de {progresso_atual["total"]}'

            batch_payload = {
                "create": lote_atual
            }

            tentativas = 0
            sucesso = False
            while tentativas < 3 and not sucesso:
                try:
                    # Validação opcional
                    for produto in lote_atual:
                        if not all([produto.get('name'), produto.get('sku'), produto.get('price')]):
                            raise Exception(f"Produto inválido no lote {numero_lote}: {produto}")

                    result = requests.post(
                        url,
                        auth=HTTPBasicAuth(WOOCOMMERCE_CONSUMER_KEY, WOOCOMMERCE_CONSUMER_SECRET),
                        json=batch_payload,
                        timeout=180
                    )

                    if result.status_code == 200:
                        print(f"Lote {numero_lote} enviado com sucesso!")
                        sucesso = True
                    else:
                        raise Exception(f"Erro API: {result.status_code} - {result.text}")

                except Exception as e:
                    tentativas += 1
                    print(f"Tentativa {tentativas} falhou para o lote {numero_lote}: {str(e)}")

                    with open(f'erro_lote_{numero_lote}_tentativa_{tentativas}.txt', 'w') as f:
                        f.write(str(e))

                    if tentativas == 3:
                        print(f"Erro crítico: lote {numero_lote} falhou após 3 tentativas.")

                time.sleep(2)  # Espera entre tentativas/lotes

        print("\nProcesso de envio concluído!")
        progresso_atual['status'] = 'Concluído!'

        return jsonify({
            'mensagem': 'Produtos enviados com sucesso.',
            'dados': produtos_processados
        })

    except Exception as erro_geral:
        print(f"Erro geral no envio: {str(erro_geral)}")
        with open('erro_geral_envio.txt', 'w') as f:
            f.write(str(erro_geral))
        return jsonify({'erro': str(erro_geral)})