import bcrypt
from flask import jsonify, request, current_app
from datetime import datetime, timedelta

from sqlalchemy.orm import aliased
from sqlalchemy import func
from app.models import Customer, Payment, Route, Session, City, Bus, Booking
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
        city_list = []
        for city in filtered_cities:
            route = Route.query.filter_by(origin_city_id=city.id).first()
            if route is not None:
                bus = Bus.query.filter_by(id=route.bus_id).first()
                city_list.append({"name": city.city_name, "bus": bus.name if bus else None})
    else:
        all_cities = City.query.all()
        city_list = []
        for city in all_cities:
            route = Route.query.filter_by(origin_city_id=city.id).first()
            if route is not None:
                bus = Bus.query.filter_by(id=route.bus_id).first()
                city_list.append({"city_name": city.city_name, "bus": bus.name if bus else None})

    return jsonify({"cities": city_list}), 200

@swag_from('docs/buses.yml')
def buses_in_city():
    bus_id = request.args.get('bus_id')
    if bus_id:
        bus_id = int(bus_id)
        buses = [Bus.query.get(bus_id)]
        if buses[0] is None:  # If the bus does not exist
            return jsonify({"error": "Bus with given ID does not exist"}), 404
    else:
        buses = Bus.query.all()

    bus_list = []

    for bus in buses:
        routes = Route.query.filter_by(bus_id=bus.id).all()

        route_list = []
        for route in routes:
            origin_city = City.query.get(route.origin_city_id).city_name
            destination_city = City.query.get(route.destination_city_id).city_name

            route_list.append({
                "route_id": route.id,
                "origin_city": origin_city,
                "destination_city": destination_city,
                "departure_date": route.departure_time.strftime("%dth %B"),
                "departure_time": route.departure_time.strftime("%H:%M"),
                "arrival_time": route.arrival_time.strftime("%H:%M"),
                "arrival_date": route.arrival_time.strftime("%dth %B"),
            })

        bus_data = {
            'id': bus.id,
            'name': bus.name,
            'capacity': bus.capacity,
            'bus_number': bus.bus_no,
            'routes': route_list,
        }

        bus_list.append(bus_data)

    return jsonify({"buses": bus_list}), 200

@swag_from('docs/bookings.yml')
@authenticate
def get_bookings():
    Origin = aliased(City)
    Destination = aliased(City)

    bookings = current_app.db.session.query(Booking, Route, Bus, Origin, Destination).\
                join(Route, Booking.route_id == Route.id).\
                join(Bus, Route.bus_id == Bus.id).\
                join(Origin, Route.origin_city_id == Origin.id).\
                join(Destination, Route.destination_city_id == Destination.id).\
                filter(Booking.customer_id == request.user_id).all()

    bookings_list = []
    for booking, route, bus, origin_city, destination_city in bookings:
        booking_data = {
            'id': booking.id,
            'bus_name': bus.name,
            'bus_number': bus.bus_no,
            'route_id': route.id,
            'origin_city_name': origin_city.city_name,
            'destination_city_name': destination_city.city_name,
            'seat_number': booking.seats_booked,
            'booking_date': booking.created_at.strftime("%m/%d/%Y, %H:%M:%S"),
            'booking_status': booking.status
        }
        bookings_list.append(booking_data)

    return jsonify({"bookings": bookings_list}), 200

@swag_from('docs/book_bus.yml')
@authenticate
def book_bus():
    data = request.get_json()
    route_id = data.get('route_id')
    seats_booked = data.get('seats_booked')

    # Fetch the route
    route = Route.query.get(route_id)
    if not route:
        return jsonify({"error": "Route not found"}), 404

    # Check if there are enough seats available
    total_booked_seats = current_app.db.session.query(func.sum(Booking.seats_booked)).filter(Booking.route_id == route_id).scalar() or 0
    available_seats = route.bus.capacity - total_booked_seats

    if seats_booked > available_seats:
        return jsonify({"error": "Not enough seats available"}), 400

    # Create a new booking
    new_booking = Booking(
        customer_id=request.user_id, 
        route_id=route_id, 
        seats_booked=seats_booked, 
        status='pending'
    )

    current_app.db.session.add(new_booking)
    current_app.db.session.commit()

    return jsonify({"booking_id": new_booking.id, "message": "Booking successful, status is pending"}), 201

@swag_from('docs/payment.yml')
@authenticate
def payment():
    data = request.get_json()

    booking_id = data.get('booking_id')
    amount = data.get('amount')
    payment_method = data.get('payment_method')
    payment_status = data.get('payment_status')

    booking = Booking.query.get(booking_id)
    if not booking:
        return jsonify({'message': 'Booking not found'}), 404

    payment = Payment(
        booking_id=booking_id,
        amount=amount,
        payment_method=payment_method,
        payment_status=payment_status
    )

    current_app.db.session.add(payment)

    if payment_status == 'success':
        booking.status = 'confirmed'
        current_app.db.session.add(booking)

    current_app.db.session.commit()

    return jsonify({'message': 'Payment processed successfully'}), 200
