from flask import Blueprint

microware_bp = Blueprint('microware', __name__)

from . import routes 