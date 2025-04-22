from . import cisco_bp
from flask import jsonify, render_template, request, Response
import pandas as pd
import json
import time
from .processors import processar_cisco_data

# Variável global para armazenar o progresso
progresso_atual = {
    'loteAtual': 0,
    'total': 0,
    'status': 'Aguardando...'
}

@cisco_bp.route('/progresso')
def progresso():
    def gerar_eventos():
        while True:
            yield f"data: {json.dumps(progresso_atual)}\n\n"
            time.sleep(1)
    
    return Response(gerar_eventos(), mimetype='text/event-stream')

@cisco_bp.route('/cisco', methods=['GET'])
def listar_produtos():
    return render_template('cisco_upload.html')

@cisco_bp.route('/cisco', methods=['POST'])
def processar_arquivo():
    global progresso_atual
    arquivo = request.files.get('arquivo')
    if not arquivo:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400

    cisco_data = pd.read_excel(arquivo, sheet_name=None)

    try:
        # Gera um arquivo JSON com os dados processados
        produtos_processados = processar_cisco_data(cisco_data)
        total_produtos = len(produtos_processados)
        progresso_atual['total'] = (total_produtos + 9) // 10

        with open('produtos_processados.json', 'w') as json_file:
            json.dump(produtos_processados, json_file, ensure_ascii=False, indent=4)

        # Processa os produtos em lotes de 10
        for i in range(0, total_produtos, 10):
            lote_atual = produtos_processados[i:i+10]
            numero_lote = (i // 10) + 1
            progresso_atual['loteAtual'] = numero_lote
            progresso_atual['status'] = f'Processando lote {numero_lote} de {progresso_atual["total"]}'
            time.sleep(1)  # Simula o processamento do lote

        progresso_atual['status'] = 'Concluído!'
        return jsonify({'mensagem': 'Arquivo Excel manipulado com sucesso'})
    except Exception as e:
        progresso_atual['status'] = 'Erro!'
        return jsonify({'erro': f'Erro ao processar o arquivo: {str(e)}'}), 500 