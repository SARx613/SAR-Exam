import os
import sys
import json
import io
import time
import markdown
import tiktoken
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
file_id = None
max_retries = 60  # 60 retries * 30 seconds = 30 minutes max
retry_delay = 30

for attempt in range(max_retries):
    try:
        # Search for the exact file name
        query = "name = 'Algebre Exam 2026.pdf' and mimeType = 'application/pdf'"
        results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        items = results.get('files', [])
        
        if items:
            file_id = items[0]['id']
            print(f"Trouvé ! ID: {file_id}")
            break
        else:
            print(f"Fichier introuvable, nouvelle tentative dans {retry_delay} secondes... ({attempt+1}/{max_retries})")
            time.sleep(retry_delay)
    except Exception as e:
        print(f"Failed to fetch from Google Drive, retrying: {e}")
        time.sleep(retry_delay)

if not file_id:
    print("Le fichier 'Algebre Exam 2026.pdf' n'est pas apparu après 15 minutes d'attente.")
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
Tu es un brillant professeur de mathématiques à l'université, et tu dois produire la CORRECTION OFFICIELLE PARFAITE (visant la note de 20/20) d'un examen de 3ème année de Licence (L3) d'Algèbre.

RÈGLES ABSOLUES :
1. NE CORRIGE PAS une copie d'élève. Tu dois RÉSOUDRE TOI-MÊME l'examen de A à Z en produisant le corrigé-type officiel et final complet pour tous les exercices.
2. NE SAUTE AUCUNE QUESTION et ne résume JAMAIS les calculs.
3. Le texte ci-dessous a été extrait d'un PDF, déduis logiquement les symboles mathématiques manquants.
4. RÈGLE CRUCIALE DE FORMATAGE LATEX : Tu dois impérativement utiliser le formatage LaTeX natif complet pour toutes les mathématiques (\( \), \[ \], $$, $, \begin{{pmatrix}}, etc). Les équations doivent être parfaitement rédigées.

Voici le sujet d'examen intégral à résoudre de la 1ère à la toute dernière ligne :

{extracted_text}
"""

# Calculate input tokens to strictly avoid TPM Rate Limit on Groq (8000 max for gpt-oss-120b)
try:
    encoding = tiktoken.get_encoding("cl100k_base")
    input_token_count = len(encoding.encode(prompt))
except Exception as e:
    input_token_count = 1500 # rough estimate if tiktoken fails
    
safety_buffer = 150
answer_markdown = ""

system_role = "You are a brilliant, meticulous university mathematics professor. You solve exams perfectly, providing full calculations step by step without skipping anything. You never act as a grader correcting an ongoing copy, you only produce the absolute master solution key. Crucially, use advanced LaTeX mathematically."

# Validation Loop System
for attempt in range(1, 4):
    if attempt <= 2:
        model_name = "openai/gpt-oss-120b"
        max_toks = 8000 - input_token_count - safety_buffer
    else:
        model_name = "llama-3.3-70b-versatile" # 12K TPM limit fallback
        max_toks = 12000 - input_token_count - safety_buffer
        
    if max_toks < 1000: max_toks = 4000
    
    print(f"--- Attempt {attempt}: Generating correction with {model_name} (max_tokens={max_toks}) ---")
    try:
        resp = client.chat.completions.create(
            messages=[{"role": "system", "content": system_role}, {"role": "user", "content": prompt}],
            model=model_name,
            temperature=0.1,
            max_tokens=max_toks
        )
        current_answer = resp.choices[0].message.content or ""
        
        # Validation checks
        if len(current_answer) < 3000:
            print("Output too short! It was likely cut off violently. Rejecting this output.")
            continue
            
        print("Model finished generation. Launching Llama-3.3-70B validator to check output quality...")
        validator_prompt = f"""
You are an automated quality assurance bot. Read the following mathematical exam correction.
Your job is to check for a critical failure:
Did the text get abruptly cut off at the very end mid-sentence, mid-equation, mid-matrix, or entirely fail to complete the exam? (For example, ending in `\\begin{{pmatrix}}1&` or `+f(\\dots` is a catastrophic cutoff).

If you detect ANY cutoff or incompleteness, output ONLY the word "NO".
If the document appears perfectly completed to the end and concludes naturally, output ONLY the word "YES".

Document to check:
{current_answer}
"""
        val_resp = client.chat.completions.create(
            messages=[{"role": "user", "content": validator_prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=20
        )
        val_decision = val_resp.choices[0].message.content.strip().upper()
        
        if "YES" in val_decision:
            print("Validation PASSED! The output is clean and completed.")
            answer_markdown = current_answer
            break
        else:
            print("Validation FAILED (incomplete, cut off, or wrong LaTeX delimiters). Trying again...")
            answer_markdown = current_answer # Keep it just in case next attempts fail worse
            
    except Exception as e:
        print(f"Error during attempt {attempt}: {e}")

if not answer_markdown:
    print("Fatal Error: All models completely failed to generate any response.")
    sys.exit(1)

print("Processing output and generating HTML...")
html_content = markdown.markdown(answer_markdown, extensions=['extra', 'codehilite', 'mdx_math'])

# Build final webpage structure with font-size: 22px
html_page = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Correction - Algèbre Exam 2026</title>

    <!-- MathJax for rendering LaTeX math formulas -->
    <script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>

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
            font-size: 24px; /* VERY LARGE FONT AS REQUESTED */
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
