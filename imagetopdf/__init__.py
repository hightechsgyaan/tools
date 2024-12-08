from flask import Flask
from imagetopdf.views import imagetopdf_bp  # Import your Blueprint

def create_app():
    """
    Factory function to create and configure the Flask application.
    """
    app = Flask(__name__)
    app.register_blueprint(imagetopdf_bp, url_prefix='/api')
    return app

# For debugging locally
if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
