from . import hp_bp
from flask import jsonify, render_template, request
import pandas as pd
import json
from .processors import processar_hp_data

@hp_bp.route('/hp', methods=['GET'])
def listar_produtos():
    return render_template('hp_upload.html')

@hp_bp.route('/hp', methods=['POST'])
def processar_arquivo():
    arquivo_produtos = request.files.get('arquivo_produtos')
    arquivo_precos = request.files.get('arquivo_precos')
    
    if not arquivo_produtos or not arquivo_precos:
        return jsonify({'erro': 'Por favor, envie ambos os arquivos (produtos e preços)'}), 400

    try:
        produtos_processados = processar_hp_data(arquivo_produtos, arquivo_precos)
            
        return jsonify({
            'mensagem': 'Arquivos Excel processados com sucesso',
            'dados': produtos_processados
        })

    except Exception as e:
        print(f"\nErro durante o processamento: {str(e)}")
        return jsonify({'erro': f'Erro ao processar os arquivos: {str(e)}'}), 500
