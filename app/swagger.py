from flasgger import Swagger
swagger = Swagger()

def configure_swagger(app):
    app.config["SWAGGER"] = {
        "title": "Backend APIs",
        "uiversion": 3,
        "description": "This is a sample description",
        "version": "1.0.2",
        "termsOfService": "link here",
        "contact": {"email": "email here"},
        "ui_params": {"displayRequestDuration": "true"},
    }
    swagger.init_app(app)