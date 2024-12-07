from flask import Flask, request, Response, send_file, jsonify, session
from pdf2image import convert_from_path
from fpdf import FPDF
import pytesseract
import os
import psutil
import time
from PyPDF2 import PdfMerger
import requests
import base64
from google.cloud import vision
from google.cloud.vision import Image as VisionImage
import io

# Setup Flask App
app = Flask(__name__)

# Set the secret key for session management (it should be kept secret in a real app)
app.secret_key = os.urandom(24)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Google Vision API Key setup
VISION_API_KEY = "AIzaSyCQBRwD_g5JPJ1Qmxj5ysW7qJIJzNpryJU"
VISION_API_URL = "https://vision.googleapis.com/v1/images:annotate"

# Function to download a font from URL
def download_font(url, font_name, font_path):
    response = requests.get(url)
    if response.status_code == 200:
        with open(font_path, 'wb') as f:
            f.write(response.content)
        print(f"Font {font_name} downloaded successfully.")
    else:
        print(f"Failed to download font: {font_name}")

def get_memory_usage():
    """Get the current memory usage of this process."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)  # Memory in MB

def perform_ocr_google(image):
    """Perform OCR on an image using Google Cloud Vision API with the provided API key."""
    # Convert the PIL image to byte data
    image_byte_array = io.BytesIO()
    image.save(image_byte_array, format='PNG')
    image_byte_array.seek(0)

    # Encode image byte array to base64
    encoded_image = base64.b64encode(image_byte_array.getvalue()).decode('utf-8')

    # Prepare the request payload with base64 encoded image
    payload = {
        "requests": [
            {
                "image": {
                    "content": encoded_image
                },
                "features": [
                    {
                        "type": "TEXT_DETECTION"
                    }
                ]
            }
        ]
    }

    # Send the request to the Vision API
    response = requests.post(VISION_API_URL, json=payload, params={"key": VISION_API_KEY})
    if response.status_code == 200:
        result = response.json()
        if 'responses' in result and 'textAnnotations' in result['responses'][0]:
            return result['responses'][0]['textAnnotations'][0]['description']
        else:
            return ""  # If no text found
    else:
        return f"Error: {response.status_code}, {response.text}"

@app.route('/')
def upload_form():
    """Render the upload form."""
    return '''
    <!doctype html>
    <title>Upload PDF for OCR</title>
    <h1>Upload a PDF File</h1>
    <form id="upload-form" enctype="multipart/form-data">
        <input type="file" id="file" name="file" accept=".pdf" required>
        <br><br>
        <label for="lang">Select Language:</label>
        <select id="lang" name="lang">
            <option value="english">English</option>
            <option value="sanskrit">Sanskrit</option>
            <option value="hindi">Hindi</option>
        </select>
        <br><br>
        <button type="button" onclick="uploadFile()">Upload and Process</button>
    </form>
    <div id="upload-progress"></div>
    <div id="processing-progress"></div>

    <script>
        function uploadFile() {
            const fileInput = document.getElementById("file");
            const langSelect = document.getElementById("lang");
            if (!fileInput.files.length) {
                alert("Please select a PDF file to upload.");
                return;
            }

            const formData = new FormData();
            formData.append("file", fileInput.files[0]);
            formData.append("lang", langSelect.value);

            const xhr = new XMLHttpRequest();
            xhr.open("POST", "/upload", true);

            xhr.upload.onprogress = function (e) {
                if (e.lengthComputable) {
                    const percentComplete = Math.round((e.loaded / e.total) * 100);
                    document.getElementById("upload-progress").innerHTML = `Uploading: ${percentComplete}%`;
                }
            };

            xhr.onload = function () {
                if (xhr.status === 200) {
                    document.getElementById("upload-progress").innerHTML = "Upload complete! Starting processing...";
                    startProcessing();
                } else {
                    document.getElementById("upload-progress").innerHTML = "Error during upload.";
                }
            };

            xhr.send(formData);
        }

        function startProcessing() {
            const eventSource = new EventSource("/process");
            const progressDiv = document.getElementById("processing-progress");
            progressDiv.innerHTML = "Processing Started...<br>";

            eventSource.onmessage = function (event) {
                if (event.data === "DONE") {
                    progressDiv.innerHTML += '<a href="/download" target="_blank">Download Combined Extracted PDF</a>';
                    eventSource.close();
                } else {
                    progressDiv.innerHTML += event.data + "<br>";
                }
            };

            eventSource.onerror = function () {
                progressDiv.innerHTML += "Error during processing.<br>";
                eventSource.close();
            };
        }
    </script>
    '''

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload."""
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    lang = request.form.get('lang', 'english')  # Get the selected language from form
    if not file.filename.endswith('.pdf'):
        return jsonify({"error": "File must be a PDF"}), 400

    pdf_path = os.path.join(UPLOAD_FOLDER, 'uploaded_file.pdf')
    file.save(pdf_path)

    # Save the selected language to be used later
    session['lang'] = lang

    return jsonify({"message": "File uploaded successfully"}), 200

@app.route('/process', methods=['GET'])
def process_file():
    """Process the uploaded file page-by-page and generate a combined PDF."""
    pdf_path = os.path.join(UPLOAD_FOLDER, 'uploaded_file.pdf')
    if not os.path.exists(pdf_path):
        return Response("Error: File not found.", content_type='text/event-stream')

    lang = session.get('lang', 'english')  # Retrieve language from session
    combined_pdf_path = os.path.join(OUTPUT_FOLDER, 'combined_text.pdf')

    def generate_progress():
        try:
            yield "data: Starting PDF processing...\n\n"
            initial_ram = get_memory_usage()
            yield f"data: Initial RAM usage: {initial_ram:.2f} MB\n\n"

            # Convert PDF to images
            images = convert_from_path(pdf_path, dpi=150)
            num_pages = len(images)
            yield f"data: PDF contains {num_pages} page(s).\n\n"

            interim_pdfs = []

            # Download font before processing
            font_url = 'https://www.1001fonts.com/download/font/dejavu-sans.book.ttf'
            font_name = 'DejaVuSans'
            font_path = os.path.join(OUTPUT_FOLDER, f'{font_name}.ttf')
            download_font(font_url, font_name, font_path)

            for i, image in enumerate(images):
                yield f"data: Processing page {i + 1}...\n\n"

                # Extract text using OCR based on language choice
                if lang == 'english':
                    text = pytesseract.image_to_string(image)
                else:
                    text = perform_ocr_google(image)

                yield f"data: Page {i + 1} processed. Text length: {len(text)} characters.\n\n"

                # Save text to a temporary PDF
                page_pdf_path = os.path.join(OUTPUT_FOLDER, f'page_{i + 1}.pdf')
                save_text_to_pdf(f"Page {i + 1}\n{text}", page_pdf_path, font_path)
                interim_pdfs.append(page_pdf_path)

                yield f"data: Interim PDF for page {i + 1} saved.\n\n"
                yield f"data: Current RAM usage: {get_memory_usage():.2f} MB\n\n"

            # Combine interim PDFs
            yield "data: Combining all pages into a single PDF...\n\n"
            merge_pdfs(interim_pdfs, combined_pdf_path)

            # Clean up interim PDFs
            for pdf in interim_pdfs:
                os.remove(pdf)

            yield f"data: Combined PDF saved to {combined_pdf_path}.\n\n"

            final_ram = get_memory_usage()
            yield f"data: Final RAM usage: {final_ram:.2f} MB\n\n"
            yield "data: DONE\n\n"
        except Exception as e:
            yield f"data: Error: {str(e)}\n\n"

    return Response(generate_progress(), content_type='text/event-stream')

def save_text_to_pdf(text, output_path, font_path):
    """Save the extracted text to a new PDF file using the downloaded font."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Use the downloaded font
    try:
        pdf.add_font('DownloadedFont', '', font_path, uni=True)
        pdf.set_font('DownloadedFont', '', 12)
    except Exception as e:
        print(f"Warning: Error using downloaded font, trying Courier: {str(e)}")
        pdf.set_font('Courier', '', 12)  # Use a default font if necessary

    pdf.multi_cell(0, 10, text)
    pdf.output(output_path)

def merge_pdfs(pdf_paths, output_path):
    """Combine multiple PDFs into a single PDF."""
    merger = PdfMerger()
    for pdf in pdf_paths:
        merger.append(pdf)
    merger.write(output_path)
    merger.close()

@app.route('/download', methods=['GET'])
def download_pdf():
    """Download the combined PDF."""
    combined_pdf_path = os.path.join(OUTPUT_FOLDER, 'combined_text.pdf')
    if not os.path.exists(combined_pdf_path):
        return "Error: Combined PDF file not found.", 404

    return send_file(combined_pdf_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=3000)
