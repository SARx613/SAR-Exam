import os
import sys
import json
import io
import markdown
import fitz  # PyMuPDF
from groq import Groq
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# 1. Configuration & Secrets
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS")

if not GROQ_API_KEY:
    print("Error: Missing GROQ_API_KEY.")
    sys.exit(1)

if not GOOGLE_CREDENTIALS_JSON:
    print("Error: Missing GOOGLE_CREDENTIALS. You must set this environment variable with the Service Account JSON.")
    sys.exit(1)

print("Connecting to Google Drive...")
try:
    # Load credentials from the JSON string
    creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    creds = Credentials.from_service_account_info(
        creds_dict, 
        scopes=['https://www.googleapis.com/auth/drive.readonly']
    )
    drive_service = build('drive', 'v3', credentials=creds)
except Exception as e:
    print(f"Failed to authenticate with Google Drive: {e}")
    sys.exit(1)

print("Searching for 'Algebre Exam 2026.pdf' in Google Drive...")
try:
    # Search for the exact file name
    query = "name = 'Algebre Exam 2026.pdf' and mimeType = 'application/pdf'"
    results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    
    if not items:
        print("Could not find a file named precisely 'Algebre Exam 2026.pdf' shared with the Service Account.")
        sys.exit(1)
        
    file_id = items[0]['id']
    print(f"Found file! ID: {file_id}")
    
except Exception as e:
    print(f"Error accessing Google Drive: {e}")
    sys.exit(1)

print("Downloading the PDF...")
pdf_path = "downloaded_exam.pdf"
try:
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    
    with open(pdf_path, 'wb') as f:
        f.write(fh.getvalue())
        
except Exception as e:
    print(f"Error downloading from Google Drive. Ensure the Service Account has 'Viewer' permission on the file: {e}")
    sys.exit(1)

print("Extracting text from the PDF...")
extracted_text = ""
try:
    doc = fitz.open(pdf_path)
    for page in doc:
        extracted_text += page.get_text() + "\n"
    doc.close()
except Exception as e:
    print(f"Error reading PDF: {e}")
    sys.exit(1)

if not extracted_text.strip():
    print("Warning: The PDF text was completely empty. It might be composed only of scanned images. Groq text api will likely fail.")

print("Successfully extracted text. Sending to Groq...")

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

# Generate an effective prompt requesting L3 Math level assistance
prompt = f"""
Tu es un professeur de mathématiques expert et hautement qualifié, spécialisé dans l'enseignement universitaire en 3ème année de Licence (L3).
Voici ci-dessous le contenu textuel extrait d'un examen PDF nommé "Algèbre Exam 2026". 

ATTENTION: Le texte ayant été extrait d'un PDF, il est possible que certaines équations ou symboles mathématiques aient de légères erreurs de formatage ou d'OCR. 
Utilise ta grande expertise pour déduire le sens exact des équations, résoudre les problèmes posés, et fournir des réponses claires, détaillées, étape par étape avec un très haut niveau de rigueur mathématique. Formate toutes les mathématiques de manière propre pour qu'elles soient lisibles.

Voici l'examen :

{extracted_text}
"""

try:
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are a helpful, brilliant mathematics professor."},
            {"role": "user", "content": prompt}
        ],
        model="llama-3.3-70b-versatile",
        temperature=0.2, # Low temperature for analytical accuracy
        max_tokens=6000
    )
    answer_markdown = chat_completion.choices[0].message.content
except Exception as e:
    print(f"Error communicating with Groq API: {e}")
    sys.exit(1)

print("Processing output and generating HTML...")

# Convert Markdown to HTML
html_content = markdown.markdown(answer_markdown, extensions=['extra', 'codehilite'])

# Build final webpage structure with font-size: 22px
html_page = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Correction - Algèbre Exam 2026</title>
    <!-- Use Google Fonts for better aesthetics -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Outfit:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0f172a;
            --text-color: #f8fafc;
            --accent-color: #3b82f6;
            --surface-color: #1e293b;
        }}
        body {{
            margin: 0;
            padding: 0;
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Inter', sans-serif;
            display: flex;
            justify-content: center;
            font-size: 22px; /* VERY LARGE FONT AS REQUESTED */
            line-height: 1.6;
            padding-bottom: 5rem;
        }}
        .container {{
            max-width: 1000px;
            width: 90%;
            margin: 3rem auto;
            background: var(--surface-color);
            padding: 3rem;
            border-radius: 16px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
        }}
        h1, h2, h3 {{
            font-family: 'Outfit', sans-serif;
            color: var(--accent-color);
        }}
        pre {{
            background: #000;
            padding: 1rem;
            border-radius: 8px;
            overflow-x: auto;
        }}
        code {{
            font-family: monospace;
            background: #000;
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Correction de l'Examen d'Algèbre 2026</h1>
        <hr style="border: 0; border-top: 1px solid #334155; margin-bottom: 2rem;">
        <div class="content">
            {html_content}
        </div>
    </div>
</body>
</html>
"""

os.makedirs("docs", exist_ok=True)
with open("docs/index.html", "w", encoding="utf-8") as f:
    f.write(html_page)

print("Done! HTML generated successfully at docs/index.html.")
