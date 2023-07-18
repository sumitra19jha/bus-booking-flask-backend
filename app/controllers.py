import bcrypt
from flask import jsonify, request, current_app
from datetime import datetime, timedelta
from app.models import Customer, Session, City, Bus, Booking
from flasgger import swag_from
from app.utils import authenticate
from app.mail import generate_random_session_id, send_otp, verify_otp

@swag_from('docs/signup.yml')
def signup():
    data = request.get_json()

    first_name = data.get('first_name')
    last_name = data.get('last_name', '')
    email = data.get('email')
    password = data.get('password')

    if not all([first_name, email, password]):
        return jsonify({"error": "First name, email and password are required"}), 400

    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
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
        password=hashed_password.decode("utf-8"),
    )
    current_app.db.session.add(new_customer)
    try:
        current_app.db.session.commit()
        send_otp(email)
    except Exception as e:
        current_app.db.session.rollback()
        return jsonify({"error": "Error occurred while signing up. Please try again."}), 500

    return jsonify({"message": "Signup successful. Please verify your email with the OTP sent"}), 200

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
    print(password.encode("utf-8"))
    print(customer.password.encode("utf-8"))
    if not bcrypt.checkpw(password.encode("utf-8"), customer.password.encode("utf-8")):
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

@swag_from('docs/cities.yml')
def cities():
    search_query = request.args.get('query')
    if search_query:
        filtered_cities = City.query.filter(City.city_name.ilike(f"%{search_query}%")).all()
        city_list = [city.city_name for city in filtered_cities]
    else:
        all_cities = City.query.all()
        city_list = [city.city_name for city in all_cities]

    return jsonify({"cities": city_list}), 200

@swag_from('docs/buses.yml')
def buses_in_city():
    city_id = request.args.get('city_id')
    if city_id == None:
        return jsonify({"error": "City ID is required"}), 400
    else:
        city_id = int(city_id)
    
    buses = Bus.query.filter(Bus.city_id == city_id).all()
    bus_list = []

    for bus in buses:
        bus_data = {
            'id': bus.id,
            'city_id': bus.city_id,
            'name': bus.name,
            'capacity': bus.capacity,
            'bus_number': bus.bus_no,
            # 'departure_time': bus.departure_time.strftime("%H:%M"),
            # 'arrival_time': bus.arrival_time.strftime("%H:%M"),
            # 'bus_company': bus.bus_company.company_name,
            # 'available_seats': bus.capacity - len(bus.bookings),
            # 'price': bus.price
        }
        bus_list.append(bus_data)

    return jsonify({"buses": bus_list}), 200

@swag_from('docs/bookings.yml')
@authenticate
def get_bookings():
    bookings = Booking.query.filter_by(customer_id=request.user_id).all()
    bookings_list = []
    for booking in bookings:
        booking_data = {
            'id': booking.id,
            'bus_id': booking.bus_id,
            'seat_number': booking.seats_booked,
            'booking_date': booking.booking_date
        }
        bookings_list.append(booking_data)

    return jsonify({"bookings": bookings_list}), 200

@swag_from('docs/book_bus.yml')
@authenticate
def book_bus():
    data = request.get_json()
    bus_id = data.get('bus_id')
    seat_number = data.get('seats_booked')
    booking_date = data.get('booking_date')

    if not all([bus_id, seat_number]):
        return jsonify({"error": "Bus id and seat number are required"}), 400

    bus = Bus.query.filter(Bus.id == bus_id).first()
    if not bus:
        return jsonify({"error": "Bus not found"}), 404

    if seat_number < 1 or seat_number > bus.capacity:
        return jsonify({"error": "Seat number is invalid"}), 400

    booking = Booking.query.filter_by(bus_id=bus_id, seats_booked=seat_number, booking_date=booking_date).first()
    if booking:
        return jsonify({"error": "Seat is already booked"}), 400

    new_booking = Booking(customer_id=request.user_id, bus_id=bus_id, booking_date=booking_date, seats_booked=seat_number)
    current_app.db.session.add(new_booking)

    try:
        current_app.db.session.commit()
    except:
        current_app.db.session.rollback()
        return jsonify({"error": "Error occurred while booking. Please try again."}), 500

    return jsonify({"message": "Booking successful", "booking_id": new_booking.id}), 200
