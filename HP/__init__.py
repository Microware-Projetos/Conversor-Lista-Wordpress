from flask import Blueprint

hp_bp = Blueprint('hp', __name__)

from . import routes 