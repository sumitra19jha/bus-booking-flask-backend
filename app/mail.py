import os
import secrets
import random
from flask_mail import Mail, Message

mail = Mail()
otp_store = {}

def configure_mail(app):
    mail.init_app(app)

def send_otp(email):
    otp = random.randint(100000, 999999)

    msg = Message(
        'OTP for email verification',
        sender='sumitra19jha@gmail.com',
        recipients=[email]
    )
    msg.body = f'Your OTP is {otp}'
    mail.send(msg)
    otp_store[email] = otp

def verify_otp(email, otp):
    stored_otp = otp_store.get(email)
    return otp == stored_otp

def generate_random_session_id():
    return secrets.token_hex(16)
