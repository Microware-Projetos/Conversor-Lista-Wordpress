from flask import Blueprint

cisco_bp = Blueprint('cisco', __name__)

from . import routes 