from . import hp_bp
from flask import jsonify, render_template, request

@hp_bp.route('/hp', methods=['GET'])
def upload_page():
    return render_template('hp_upload.html')

@hp_bp.route('/hp', methods=['POST'])
def processar_arquivo():
    arquivo = request.files.get('arquivo')
    if not arquivo:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400

    # Aqui você pode implementar sua lógica para processar o arquivo Excel
    return jsonify({'mensagem': 'Arquivo Excel recebido com sucesso'})

@hp_bp.route('/hp/produtos')
def listar_produtos():
    # Aqui você pode implementar sua lógica para listar produtos
    return jsonify({'mensagem': 'Lista de produtos HP'})

@hp_bp.route('/hp/produtos/<id>')
def obter_produto(id):
    # Aqui você pode implementar sua lógica para obter um produto específico
    return jsonify({'mensagem': f'Produto HP {id}'}) 