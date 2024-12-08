# tools/pdftools/mergepdf.py

from flask import Blueprint, request, jsonify, send_file
from PyPDF2 import PdfMerger
import os
import uuid

# Initialize Blueprint
mergepdf_bp = Blueprint('mergepdf', __name__)

# Define the upload folder
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@mergepdf_bp.route("/merge-pdfs", methods=["POST"])
def merge_pdfs():
    """
    API endpoint to merge multiple PDF files into one.
    """
    try:
        if "pdfs" not in request.files:
            return jsonify({"error": "No PDF files uploaded"}), 400

        files = request.files.getlist("pdfs")
        pdf_paths = []
        for file in files:
            if file.filename.lower().endswith("pdf"):
                filename = f"{uuid.uuid4().hex}_{file.filename}"
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                pdf_paths.append(filepath)
            else:
                return jsonify({"error": f"Unsupported file type: {file.filename}"}), 400

        merger = PdfMerger()
        for pdf in pdf_paths:
            merger.append(pdf)

        output_pdf_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4().hex}_merged.pdf")
        merger.write(output_pdf_path)
        merger.close()

        return send_file(output_pdf_path, as_attachment=True)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
