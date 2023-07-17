import secrets
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timedelta
from werkzeug.security import check_password_hash, generate_password_hash
from app.models import Customer, Session, City, Bus, Booking
from flasgger import swag_from
from app.mail import generate_random_session_id, send_otp, verify_otp
from app.utils import authenticate

views = Blueprint("views", __name__)

@views.route('/signup', methods=['POST'])
@swag_from('docs/signup.yml')
def signup():
    data = request.get_json()

    first_name = data.get('first_name')
    last_name = data.get('last_name', '')
    email = data.get('email')
    password = data.get('password')

    if not all([first_name, email, password]):
        return jsonify({"error": "First name, email and password are required"}), 400

    hashed_password = generate_password_hash(password)
    existing_customer = Customer.query.filter_by(email=email).first()

    if existing_customer and existing_customer.email_verified == 'unverified':
        send_otp(email)
        return jsonify({"message": "Please verify your email with the OTP sent"}), 200
    elif existing_customer:
        return jsonify({"error": "Email already taken"}), 400

    new_customer = Customer(
        first_name=first_name,
        last_name=last_name,
        email=email,
        password=hashed_password,
    )
    current_app.db.session.add(new_customer)
    try:
        current_app.db.session.commit()
        send_otp(email)
    except:
        current_app.db.session.rollback()
        return jsonify({"error": "Error occurred while signing up. Please try again."}), 500

    return jsonify({"message": "Signup successful. Please verify your email with the OTP sent"}), 200

@views.route('/verify', methods=['POST'])
@swag_from('docs/verify.yml')
def verify():
    data = request.get_json()
    email = data.get('email')
    otp = data.get('otp')

    if not all([email, otp]):
        return jsonify({"error": "Email and OTP are required"}), 400

    customer = Customer.query.filter_by(email=email).first()
    if not customer:
        return jsonify({"error": "No customer with that email found"}), 404

    if not verify_otp(email, otp):
        return jsonify({"error": "OTP is incorrect or has expired"}), 400

    customer.email_verified = 'verified'

    # Create a new session
    session_id = generate_random_session_id()
    valid_till = datetime.utcnow() + timedelta(days=7)  # Set session validity for 7 days
    new_session = Session(user_id=customer.id, session_id=session_id, valid_till=valid_till)
    current_app.db.session.add(new_session)

    try:
        current_app.db.session.commit()
    except:
        current_app.db.session.rollback()
        return jsonify({"error": "Error occurred while Email verification. Please try again."}), 500
    
    return jsonify({"message": "Email verified successfully", "user_id": customer.id, "session_id": session_id}), 200

@views.route('/login', methods=['POST'])
@swag_from('docs/login.yml')
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not all([email, password]):
        return jsonify({"error": "Email and password are required"}), 400

    customer = Customer.query.filter_by(email=email).first()
    if not customer:
        return jsonify({"error": "No customer with that email found"}), 404

    if not check_password_hash(customer.password, password):
        return jsonify({"error": "Incorrect password"}), 401

    # Generate and save a new session for the user
    session_id = generate_random_session_id()
    valid_till = datetime.utcnow() + timedelta(days=7)  # Set session validity for 7 days
    new_session = Session(user_id=customer.id, session_id=session_id, valid_till=valid_till)
    current_app.db.session.add(new_session)

    try:
        current_app.db.session.commit()
    except:
        current_app.db.session.rollback()
        return jsonify({"error": "Error occurred while logging in. Please try again."}), 500

    return jsonify({"message": "Login successful", "user_id": customer.id, "session_id": session_id}), 200

@views.route('/cities', methods=['GET'])
@swag_from('docs/cities.yml')
@authenticate
def cities():
    search_query = request.args.get('query')
    if search_query:
        filtered_cities = City.query.filter(City.city_name.ilike(f"%{search_query}%")).all()
        city_list = [city.city_name for city in filtered_cities]
    else:
        all_cities = City.query.all()
        city_list = [city.city_name for city in all_cities]

    return jsonify({"cities": city_list}), 200

@views.route('/buses', methods=['GET'])
@swag_from('docs/buses.yml')
def buses_in_city():
    buses = Bus.query.all()
    bus_list = []
    for bus in buses:
        bus_data = {
            'id': bus.id,
            'name': bus.name,
            'capacity': bus.capacity,
            'city_id': bus.city_id,
            'created_at': bus.created_at,
            'updated_at': bus.updated_at
        }
        bus_list.append(bus_data)
    return jsonify(bus_list), 200


@views.route('/bookings', methods=['GET'])
@swag_from('docs/bookings.yml')
@authenticate
def get_bookings():
    bookings = Booking.query.all()
    booking_list = []
    for booking in bookings:
        booking_info = {
            'booking_id': booking.id,
            'customer_id': booking.customer_id,
            'bus_id': booking.bus_id,
            'booking_date': booking.booking_date.strftime('%Y-%m-%d %H:%M:%S'),
            'seats_booked': booking.seats_booked
        }
        booking_list.append(booking_info)
    return jsonify({'bookings': booking_list}), 200

@views.route('/book_bus', methods=['POST'])
@swag_from('docs/book_bus.yml')
@authenticate
def book_bus():
    data = request.get_json()
    user_id = data.get('user_id')
    session_id = data.get('session_id')
    bus_id = data.get('bus_id')
    booking_date = data.get('booking_date')
    seats_booked = data.get('seats_booked')

    if not all([user_id, session_id, bus_id, booking_date, seats_booked]):
        return jsonify({"error": "User ID, Session ID, Bus ID, Booking Date, and Seats Booked are required"}), 400

    session = Session.query.filter_by(user_id=user_id, session_id=session_id, status='active').first()
    if not session:
        return jsonify({"error": "Invalid session"}), 401

    bus = Bus.query.get(bus_id)
    if not bus:
        return jsonify({"error": "Invalid bus ID"}), 404

    if seats_booked > bus.capacity:
        return jsonify({"error": "Seats booked exceed bus capacity"}), 400

    booking_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
    total_booked_seats = Booking.query.filter_by(bus_id=bus_id, booking_date=booking_date).sum('seats_booked')
    if total_booked_seats is None:
        total_booked_seats = 0

    available_seats = bus.capacity - total_booked_seats
    if seats_booked > available_seats:
        return jsonify({"error": "Seats booked exceed available seats"}), 400

    new_booking = Booking(
        customer_id=session.user_id,
        bus_id=bus_id,
        booking_date=booking_date,
        seats_booked=seats_booked
    )
    current_app.db.session.add(new_booking)
    try:
        current_app.db.session.commit()
    except:
        current_app.db.session.rollback()
        return jsonify({"error": "Error occurred while booking the bus. Please try again."}), 500

    return jsonify({"message": "Bus booked successfully"}), 200
