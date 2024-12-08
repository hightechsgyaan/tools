from flask import Flask
from imagetopdf.views import imagetopdf_bp  # Adjust path if necessary

app = Flask(__name__)

# Register Blueprint
app.register_blueprint(imagetopdf_bp, url_prefix='/api')

if __name__ == '__main__':
    app.run(debug=True)
