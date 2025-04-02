from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return 'Bem-vindo à minha aplicação Flask!'



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
