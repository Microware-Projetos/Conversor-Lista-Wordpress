from flask import Blueprint

hub2b_bp = Blueprint('hub2b', __name__)

from . import routes 