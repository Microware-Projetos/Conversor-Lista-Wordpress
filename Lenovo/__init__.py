from flask import Blueprint

lenovo_bp = Blueprint('lenovo', __name__)

from . import routes 