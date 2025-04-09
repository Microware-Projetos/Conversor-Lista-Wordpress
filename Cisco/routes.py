from . import cisco_bp
from flask import jsonify, render_template, request
import pandas as pd
import json
from .processors import processar_cisco_data

@cisco_bp.route('/cisco', methods=['GET'])
def listar_produtos():
    return render_template('cisco_upload.html')

@cisco_bp.route('/cisco', methods=['POST'])
def processar_arquivo():
    arquivo = request.files.get('arquivo')
    if not arquivo:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400

    cisco_data = pd.read_excel(arquivo, sheet_name=None)

    try:
        # Gera um arquivo JSON com os dados processados
        produtos_processados = processar_cisco_data(cisco_data)
        with open('produtos_processados.json', 'w') as json_file:
            json.dump(produtos_processados, json_file, ensure_ascii=False, indent=4)
    except Exception as e:
        return jsonify({'erro': f'Erro ao processar o arquivo: {str(e)}'}), 500

    return jsonify({'mensagem': 'Arquivo Excel manipulado com sucesso'}) 