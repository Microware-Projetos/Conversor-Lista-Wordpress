from flask import Flask, render_template, request, jsonify
from Lenovo import lenovo_bp
from HP import hp_bp
from Cisco import cisco_bp

app = Flask(__name__, static_folder='static')

# Registrar os blueprints
app.register_blueprint(lenovo_bp)
app.register_blueprint(hp_bp)
app.register_blueprint(cisco_bp)

@app.route('/')
def home():
    return render_template('home.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
