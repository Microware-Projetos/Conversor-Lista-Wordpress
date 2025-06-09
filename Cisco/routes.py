from . import cisco_bp
from flask import jsonify, render_template, request, Response
import pandas as pd
import json
import time
from .processors import processar_cisco_data
import os

# Variável global para armazenar o progresso
progresso_atual = {
    'loteAtual': 0,
    'total': 0,
    'status': 'Aguardando...'
}

def get_dolar_file_path():
    return os.path.join(os.path.dirname(__file__), 'dolar.json')

def get_dolar_value():
    try:
        with open(get_dolar_file_path(), 'r') as f:
            data = json.load(f)
            return data['valor']
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return 5.0  # valor padrão

def save_dolar_value(valor):
    with open(get_dolar_file_path(), 'w') as f:
        json.dump({'valor': float(valor)}, f)

@cisco_bp.route('/cisco/dolar', methods=['GET'])
def get_dolar():
    return jsonify({'valor': get_dolar_value()})

@cisco_bp.route('/cisco/dolar', methods=['POST'])
def update_dolar():
    try:
        data = request.get_json()
        valor = data.get('valor')
        if valor is None or not isinstance(valor, (int, float)) or valor <= 0:
            return jsonify({'erro': 'Valor do dólar inválido'}), 400
        save_dolar_value(valor)
        return jsonify({'mensagem': 'Valor do dólar atualizado com sucesso'})
    except Exception as e:
        return jsonify({'erro': f'Erro ao atualizar valor do dólar: {str(e)}'}), 500

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
    tipo_lista = request.form.get('tipoLista')
    valor_dolar = request.form.get('valorDolar')
    
    if not arquivo:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400
    
    if not tipo_lista or tipo_lista not in ['real', 'dolar']:
        return jsonify({'erro': 'Tipo de lista inválido'}), 400
    
    try:
        # Define o header baseado no tipo de lista
        if tipo_lista == 'real':
            header_row = 15  # Header da lista em reais
        else:  # tipo_lista == 'dolar'
            header_row = 15  # Header da lista em dólar
            if not valor_dolar:
                return jsonify({'erro': 'Valor do dólar é obrigatório para lista em dólar'}), 400
            try:
                valor_dolar = float(valor_dolar)
                save_dolar_value(valor_dolar)
            except ValueError:
                return jsonify({'erro': 'Valor do dólar inválido'}), 400

        # Lê o arquivo Excel com o header apropriado
        cisco_data = pd.read_excel(arquivo, engine='calamine', header=header_row)
        
        # Processa os dados
        produtos_processados = processar_cisco_data(cisco_data, valor_dolar, tipo_lista)

        total_produtos = len(produtos_processados)
        print("Total de produtos processados: ", total_produtos)
        progresso_atual['total'] = (total_produtos + 9) // 10

        # Salva os produtos processados em um arquivo JSON
        nome_arquivo = f'produtos_cisco_{tipo_lista}.json'
        with open(nome_arquivo, 'w') as json_file:
            json.dump(produtos_processados, json_file, ensure_ascii=False, indent=4)

        # Processa os produtos em lotes de 10
        for i in range(0, total_produtos, 10):
            lote_atual = produtos_processados[i:i+10]
            numero_lote = (i // 10) + 1
            progresso_atual['loteAtual'] = numero_lote
            progresso_atual['status'] = f'Processando lote {numero_lote} de {progresso_atual["total"]}'
            time.sleep(1)  # Simula o processamento do lote

        progresso_atual['status'] = 'Concluído!'
        return jsonify({
            'mensagem': f'Arquivo Excel processado com sucesso - Lista {tipo_lista.upper()}',
            'total_produtos': total_produtos,
            'arquivo_saida': nome_arquivo
        })

    except Exception as e:
        progresso_atual['status'] = 'Erro!'
        return jsonify({
            'erro': f'Erro ao processar o arquivo: {str(e)}',
            'tipo_lista': tipo_lista
        }), 500 