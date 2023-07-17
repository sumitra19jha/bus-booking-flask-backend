import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from app.mail import configure_mail

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    load_dotenv()

    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
    app.config['MAIL_PORT'] = os.getenv('MAIL_PORT')
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS')
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')

    db.init_app(app)
    app.db = db  # Add this line to attach db instance to the app object
    configure_mail(app)

    from app.swagger import configure_swagger
    configure_swagger(app)

    from app.routes import routes
    app.register_blueprint(routes)

    return app
