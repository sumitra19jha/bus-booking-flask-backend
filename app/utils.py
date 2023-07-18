from app import db
from datetime import datetime
from flask import jsonify, request
from app.models import Session

def authenticate(func):
    def wrapper(*args, **kwargs):
        session_id = request.headers.get('Authorization')

        if not session_id or not session_id.startswith('Bearer '):
            return jsonify({"error": "Missing or invalid session ID in the header"}), 401

        session_id = session_id.replace('Bearer ', '')
        session = Session.query.filter_by(session_id=session_id, status='active').first()

        if not session:
            return jsonify({"error": "Invalid session ID"}), 401

        if session.valid_till < datetime.utcnow():
            session.status = 'logged_out'
            db.session.commit()
            return jsonify({"error": "Session expired"}), 401
        
        request.session =  session
        request.session_id = session_id
        request.user_id = session.user_id

        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper