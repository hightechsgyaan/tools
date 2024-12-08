from flask import Blueprint, request, jsonify, send_file, render_template
from PIL import Image
import os
import uuid
import tempfile
import shutil
import logging
from flask_cors import CORS

# Initialize Blueprint
imagetopdf_bp = Blueprint('imagetopdf', __name__)

# Allowed file extensions
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "bmp", "gif"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB max file size

# Logger setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# CORS Configuration
CORS(imagetopdf_bp, resources={r"/convert-to-pdf": {"origins": "https://hightechsgyaan.com"}})

def allowed_file(filename):
    """
    Check if a file has an allowed extension.
    """
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_file_size(file):
    """
    Check if the file size is under the allowed limit.
    """
    if len(file.read()) > MAX_FILE_SIZE:
        return False
    file.seek(0)  # Reset file pointer after reading size
    return True

def images_to_pdf(image_files, output_pdf, resize=False):
    """
    Convert a list of image file paths to a single PDF file.
    Optionally resize images to optimize performance.
    """
    try:
        images = []
        for img_path in image_files:
            img = Image.open(img_path).convert("RGB")
            if resize:
                img.thumbnail((1024, 1024))  # Resize to max 1024x1024
            images.append(img)
        
        # Save the first image as the PDF and append others
        images[0].save(output_pdf, save_all=True, append_images=images[1:])
        return output_pdf
    except Exception as e:
        logger.error(f"Error during PDF creation: {e}")
        raise RuntimeError(f"Failed to create PDF: {e}")

@imagetopdf_bp.route("/convert-to-pdf", methods=["GET", "POST"])
def convert_to_pdf():
    """
    Browser view and API endpoint to convert images to PDF.
    """
    if request.method == "GET":
        # Render the form for browser-based usage (if needed for testing)
        return render_template("convert_to_pdf.html")
    
    try:
        # Ensure images are uploaded
        if "images" not in request.files:
            return jsonify({"error": "No images uploaded"}), 400

        files = request.files.getlist("images")
        if not files or all(file.filename == '' for file in files):
            return jsonify({"error": "No files selected"}), 400

        # Validate and save uploaded files
        temp_dir = tempfile.mkdtemp()
        image_paths = []

        for file in files:
            if file and allowed_file(file.filename):
                if not validate_file_size(file):
                    return jsonify({"error": f"File {file.filename} is too large. Maximum size is 50MB."}), 400

                filename = f"{uuid.uuid4().hex}_{file.filename}"
                filepath = os.path.join(temp_dir, filename)
                file.save(filepath)
                image_paths.append(filepath)
            else:
                return jsonify({"error": f"Unsupported file type: {file.filename}"}), 400

        if not image_paths:
            return jsonify({"error": "No valid images found"}), 400

        # Optionally: allow users to choose custom resizing (add form for width/height)
        resize = request.form.get("resize", "false").lower() == "true"
        width = int(request.form.get("width", 1024))  # Default width to 1024 if not specified
        height = int(request.form.get("height", 1024))  # Default height to 1024

        # Apply custom resizing options
        if resize:
            logger.debug(f"Resizing images to {width}x{height}")
            for img_path in image_paths:
                img = Image.open(img_path)
                img.thumbnail((width, height))
                img.save(img_path)

        # Determine output PDF name
        user_pdf_name = request.form.get("output_name", None)
        if not user_pdf_name:
            # Default to the first uploaded image name (without extension)
            base_name = os.path.splitext(os.path.basename(image_paths[0]))[0]
            output_pdf_name = f"{base_name}.pdf"
        else:
            # Ensure the user-provided name ends with .pdf
            output_pdf_name = user_pdf_name if user_pdf_name.endswith(".pdf") else f"{user_pdf_name}.pdf"

        output_pdf_path = os.path.join(temp_dir, output_pdf_name)

        # Convert images to PDF
        pdf_path = images_to_pdf(image_paths, output_pdf_path, resize=True)

        # Return the PDF as a downloadable file
        return send_file(pdf_path, as_attachment=True, download_name=output_pdf_name)

    except Exception as e:
        logger.error(f"Error processing PDF conversion: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        # Clean up temporary files and directory
        shutil.rmtree(temp_dir, ignore_errors=True)
