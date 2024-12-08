from flask import Flask
from imagetopdf.views import imagetopdf_bp  # Import your Blueprint

def create_app():
    """
    Factory function to create and configure the Flask application.
    """
    app = Flask(__name__)

    # Register the imagetopdf Blueprint
    app.register_blueprint(imagetopdf_bp, url_prefix='/api')

    return app

# For running locally
if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)  # Runs on localhost
