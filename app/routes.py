from flask import Blueprint
from app.controllers import signup, verify, login, cities, buses_in_city, get_bookings, book_bus
from app.utils import authenticate

routes = Blueprint("routes", __name__)

routes.add_url_rule('/user/signup', view_func=signup, methods=['POST'])
routes.add_url_rule('/user/verify', view_func=verify, methods=['POST'])
routes.add_url_rule('/user/login', view_func=login, methods=['POST'])
routes.add_url_rule('/cities', view_func=cities, methods=['GET'])
routes.add_url_rule('/buses', view_func=buses_in_city, methods=['GET'])
routes.add_url_rule('/bookings', view_func=authenticate(get_bookings), methods=['GET'])
routes.add_url_rule('/book_bus', view_func=authenticate(book_bus), methods=['POST'])