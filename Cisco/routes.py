from . import cisco_bp
from flask import jsonify, render_template, request

@cisco_bp.route('/cisco', methods=['GET'])
def upload_page():
    return render_template('cisco_upload.html')

@cisco_bp.route('/cisco', methods=['POST'])
def processar_arquivo():
    arquivo = request.files.get('arquivo')
    if not arquivo:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400

    # Aqui você pode implementar sua lógica para processar o arquivo Excel
    return jsonify({'mensagem': 'Arquivo Excel recebido com sucesso'}) 