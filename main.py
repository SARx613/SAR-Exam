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

# ─────────────────────────────────────────────
# 1. Configuration & Secrets
# ─────────────────────────────────────────────
#
# MODEL_PROVIDER controls which AI backend to use:
#   "groq"          → Groq API (GPT-120B + Llama-70B fallback) — GRATUIT
#   "claude_haiku"  → Claude Haiku 4.5  ($1/$5 par MTok)   ← le plus économique
#   "claude_sonnet" → Claude Sonnet 4.6 ($3/$15 par MTok)  ← bon équilibre
#   "claude_opus"   → Claude Opus 4.7  ($5/$25 par MTok)   ← le plus puissant
#
# Pour utiliser Claude, définis aussi ANTHROPIC_API_KEY dans tes secrets.
# ─────────────────────────────────────────────

MODEL_PROVIDER = os.environ.get("MODEL_PROVIDER", "groq").lower()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS")

# Map provider names to Anthropic model identifiers
CLAUDE_MODEL_MAP = {
    "claude_haiku":  "claude-haiku-4-5",
    "claude_sonnet": "claude-sonnet-4-6",
    "claude_opus":   "claude-opus-4-7",
}

# Validate required secrets depending on chosen provider
if MODEL_PROVIDER == "groq":
    if not GROQ_API_KEY:
        print("Error: MODEL_PROVIDER=groq mais GROQ_API_KEY est absent.")
        sys.exit(1)
elif MODEL_PROVIDER in CLAUDE_MODEL_MAP:
    if not ANTHROPIC_API_KEY:
        print(f"Error: MODEL_PROVIDER={MODEL_PROVIDER} mais ANTHROPIC_API_KEY est absent.")
        sys.exit(1)
else:
    print(f"Error: MODEL_PROVIDER='{MODEL_PROVIDER}' inconnu. Choix valides : groq, claude_haiku, claude_sonnet, claude_opus")
    sys.exit(1)

if not GOOGLE_CREDENTIALS_JSON:
    print("Error: Missing GOOGLE_CREDENTIALS. You must set this environment variable with the Service Account JSON.")
    sys.exit(1)

print(f"✅ Mode sélectionné : {MODEL_PROVIDER.upper()}")

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

# Read the target filename from exam_filename.txt
target_filename = "Algebre Exam 2026.pdf" # Fallback
if os.path.exists("exam_filename.txt"):
    with open("exam_filename.txt", "r", encoding="utf-8") as f:
        content = f.read().strip()
        if content:
            target_filename = content

print(f"Searching for '{target_filename}' in Google Drive...")
file_id = None
max_retries = 60  # 60 retries * 30 seconds = 30 minutes max
retry_delay = 30

for attempt in range(max_retries):
    try:
        # Search for the exact file name
        query = f"name = '{target_filename}' and mimeType = 'application/pdf'"
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
    print(f"Le fichier '{target_filename}' n'est pas apparu après 15 minutes d'attente.")
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

print(f"Successfully extracted text. Sending to {MODEL_PROVIDER.upper()}...")

# ─── Initialize AI clients ───────────────────────────────────────────────────
groq_client = None
claude_client = None
CLAUDE_MODEL = None

# Toujours initialiser Groq si la clé est dispo (sert de fallback crédit épuisé)
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)
    if MODEL_PROVIDER == "groq":
        print("Client Groq initialisé (provider principal).")
    else:
        print("Client Groq initialisé (fallback crédit épuisé disponible).")

if MODEL_PROVIDER != "groq":
    try:
        import anthropic
        claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        CLAUDE_MODEL = CLAUDE_MODEL_MAP[MODEL_PROVIDER]
        print(f"Client Anthropic initialisé — modèle : {CLAUDE_MODEL}")
    except ImportError:
        print("Error: Le package 'anthropic' n'est pas installé. Lance : pip install anthropic")
        sys.exit(1)

# ─── Helper : call the configured AI model ───────────────────────────────────
def _call_groq_fallback(system_msg, user_msg, max_tokens):
    """Fallback Groq : GPT-OSS-120B → Llama-70B."""
    if not groq_client:
        raise Exception("Groq fallback demandé mais GROQ_API_KEY absent — impossible.")
    print("🔀 Basculement sur Groq (GPT-OSS-120B)...")
    try:
        resp = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": system_msg},
                      {"role": "user",   "content": user_msg}],
            model="openai/gpt-oss-120b",
            temperature=0.1,
            max_tokens=min(max_tokens, 8000),
        )
        text = resp.choices[0].message.content or ""
        if not text.strip():
            raise Exception("GPT-120B vide.")
        return text, False
    except Exception as e:
        print(f"GPT-120B error: {e} → fallback Llama-70B")
        resp = groq_client.chat.completions.create(
            messages=[{"role": "system", "content": system_msg},
                      {"role": "user",   "content": user_msg}],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=min(max_tokens, 8000),
        )
        text = resp.choices[0].message.content or ""
        if not text.strip():
            raise Exception("Llama-70B AUSSI vide.")
        return text, False

def call_model(system_msg, user_msg, max_tokens):
    """Appelle le provider sélectionné et retourne (texte, hit_limit)."""

    if MODEL_PROVIDER == "groq":
        return _call_groq_fallback(system_msg, user_msg, max_tokens)

    else:
        # ── Anthropic Claude (haiku / sonnet / opus) ──────────────────────────
        import anthropic

        def _is_billing_error(e):
            """Détecte les erreurs de crédit/facturation Anthropic."""
            if isinstance(e, anthropic.APIStatusError) and e.status_code == 402:
                return True
            msg = str(e).lower()
            return any(kw in msg for kw in ("credit", "billing", "balance", "quota", "payment", "insufficient"))

        for attempt in range(6):
            try:
                resp = claude_client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=max_tokens,
                    system=system_msg,
                    messages=[{"role": "user", "content": user_msg}],
                )
                text = resp.content[0].text if resp.content else ""
                hit_limit = (resp.stop_reason == "max_tokens")
                return text, hit_limit

            except anthropic.RateLimitError:
                wait = 60 * (attempt + 1)
                print(f"⏳ Rate limit Anthropic. Attente {wait}s (tentative {attempt+1}/6)...")
                time.sleep(wait)

            except Exception as e:
                if _is_billing_error(e):
                    print(f"💳 Crédit Anthropic épuisé ({e}). Basculement automatique sur Groq...")
                    return _call_groq_fallback(system_msg, user_msg, max_tokens)
                print(f"Anthropic API error: {e}")
                raise

        # Rate limit persistant après 6 tentatives → essai Groq
        print("⚠️ Rate limit Anthropic persistant après 6 tentatives. Basculement sur Groq...")
        return _call_groq_fallback(system_msg, user_msg, max_tokens)
# Generate an effective prompt requesting L3 Math level assistance
prompt = f"""
Tu es un brillant professeur de mathématiques à l'université, et tu dois produire la CORRECTION OFFICIELLE PARFAITE (visant la note de 20/20) d'un examen de 3ème année de Licence (L3) d'Algèbre.

RÈGLES ABSOLUES :
1. NE CORRIGE PAS une copie d'élève. Tu dois RÉSOUDRE TOI-MÊME l'examen de A à Z.
2. AUCUNE FAINÉANTISE. Interdiction formelle d'utiliser les expressions "il suffit de", "on peut montrer que", ou "cela peut être fait". TU DOIS EFFECTUER LA PREUVE EN ENTIER SOUS MES YEUX !
3. Aucun calcul magique. Pour les calculs de noyau, valeurs propres, décompositions de Dunford, etc., tu dois écrire la matrice, écrire le système linéaire, et le résoudre étape par étape sans sauter d'étape.
4. RÈGLE CRUCIALE DE FORMATAGE (MARKDOWN + MATHJAX) : 
   - La structure du document DOIT être en Markdown strict (utilise '#', '##' pour les titres, des tirets '-' ou des '1.' pour les listes, '**gras**').
   - INTERDICTION ABSOLUE d'utiliser les commandes structurelles LaTeX telles que \section, \subsection, \textbf, \begin{enumerate}, \item, etc.
   - Utilise LaTeX *uniquement* pour les expressions mathématiques.
   - Les équations en ligne doivent être encadrées par `$` (exemple: $x^2 + 1$).
   - Les équations hors texte doivent être centrées et encadrées par `$$` (exemple: $$ \int f(x) dx $$).
   - N'indente JAMAIS le début de tes lignes avec des espaces (cela crée des blocs de code qui cassent le rendu mathématique).
Voici le sujet d'examen intégral à résoudre de la 1ère à la toute dernière ligne avec une rigueur absolue :

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

system_role = "Tu es un professeur de mathématiques d'université intraitable et hyper-rigoureux. Tu dois fournir une copie corrigée d'excellence. INTERDICTION D'ÊTRE PARESSEUX : tu dois prouver absolument tout ce que tu affirmes et écrire tous les calculs matriciels intermédiaires. Interdiction d'utiliser les formules 'on peut voir que' ou 'il est facile de montrer'. Utilise exclusivement le Markdown pour la structure (titres, listes) et LaTeX ($ et $$) pour les mathématiques. N'utilise jamais les commandes \\section ou \\begin{enumerate}. N'indente pas tes lignes."
full_answer = ""
current_instruction = "Résous l'intégralité de l'examen de la première à la dernière question."
max_iterations = 8

# Limite de tokens selon le provider
MAX_OUTPUT_TOKENS = {
    "groq":         8000,
    "claude_haiku": 8096,
    "claude_sonnet": 16000,
    "claude_opus":  16000,
}.get(MODEL_PROVIDER, 8000)

for loop_index in range(max_iterations):
    print(f"--- GENERATION LOOP {loop_index+1} ({MODEL_PROVIDER.upper()}) ---")

    current_prompt = prompt + "\n\n" + current_instruction

    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        input_token_count = len(encoding.encode(current_prompt + system_role))
    except Exception:
        input_token_count = 2000

    safety_buffer = 200
    calc_max_tokens = MAX_OUTPUT_TOKENS - safety_buffer
    if calc_max_tokens < 1000:
        calc_max_tokens = 4000

    print(f"Appel {MODEL_PROVIDER.upper()} — max_tokens de sortie : {calc_max_tokens}")
    try:
        new_text, hit_limit = call_model(system_role, current_prompt, calc_max_tokens)
        if not new_text.strip():
            print("Le modèle a retourné une réponse vide. Arrêt de la boucle.")
            break
    except Exception as e:
        print(f"Erreur fatale lors de l'appel au modèle : {e}")
        break

    full_answer += "\n" + new_text

    # ── Détection coupure (limite de tokens atteinte) ─────────────────────────
    try:
        gen_tokens = len(encoding.encode(new_text))
    except Exception:
        gen_tokens = 0

    if hit_limit or (gen_tokens > 0 and abs(calc_max_tokens - gen_tokens) < 80):
        print(f"HARD LIMIT REACHED! ({gen_tokens} générés vs {calc_max_tokens} max). Forçage de la continuation...")
        cutoff_tail = new_text[-400:]
        current_instruction = (
            f"IMPORTANT : Ta précédente réponse a été brutalement coupée par le système à cause de la limite de texte.\n"
            f"Voici la toute fin de ton texte coupé :\n[...]\n{cutoff_tail}\n\n"
            f"Reprends la rédaction EXACTEMENT à la lettre près où tu as été coupé (sans AUCUNE phrase d'introduction) et continue la correction."
        )
        wait_time = 65 if MODEL_PROVIDER == "groq" else 5
        print(f"Attente {wait_time}s avant continuation...")
        time.sleep(wait_time)
        continue

    # ── Vérification complétude via superviseur ───────────────────────────────
    print("Génération sous la limite. Activation du Superviseur...")
    supervisor_prompt = f"""You are the Quality Assurance Supervisor. Read the original exam text:
{extracted_text}

Read the mathematical correction generated by the AI so far:
{full_answer}

Compare them. Is the correction 100% completed up to and including the FINAL exercise of the exam?
If YES, output ONLY the word: DONE
If there are any exercises, questions, or sections of the exam remaining unanswered, output a command directed to the AI telling it what to do next. For example: "Tu t'es arrêté avant la fin. Il faut maintenant corriger l'Exercice 2 et la fin du document."
"""
    try:
        if MODEL_PROVIDER == "groq" or not claude_client:
            # Mode Groq pur : superviseur = Llama-70B
            sup_resp = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": supervisor_prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.1,
                max_tokens=200,
            )
            sup_decision = sup_resp.choices[0].message.content.strip()
        else:
            # Mode Claude : on essaie Claude, fallback Groq si échec
            try:
                import anthropic
                sup_resp = claude_client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=200,
                    messages=[{"role": "user", "content": supervisor_prompt}],
                )
                sup_decision = sup_resp.content[0].text.strip()
            except Exception as e_claude:
                print(f"⚠️ Superviseur Claude échoué ({e_claude}). Basculement sur Groq Llama-70B...")
                sup_resp = groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": supervisor_prompt}],
                    model="llama-3.3-70b-versatile",
                    temperature=0.1,
                    max_tokens=200,
                )
                sup_decision = sup_resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"Superviseur en échec total : {e}. On suppose terminé.")
        break

    if any(kw in sup_decision.upper() for kw in ("DONE", "YES", "TERMINÉ", "COMPLETE")):
        print("✅ Superviseur : correction COMPLÈTE. Fin de boucle.")
        break
    else:
        print(f"Superviseur → continuation : {sup_decision}")
        current_instruction = (
            f"IMPORTANT : Tu as généré avec succès une partie du corrigé, mais le superviseur a noté que ce n'est pas terminé. "
            f"Voici sa consigne exacte pour reprendre la correction :\n\"{sup_decision}\"\n"
            f"N'écris aucune introduction, attaque directement la suite de la correction en LaTeX."
        )
        wait_time = 65 if MODEL_PROVIDER == "groq" else 10
        print(f"Attente {wait_time}s avant la prochaine itération...")
        time.sleep(wait_time)

answer_markdown = full_answer
if not answer_markdown.strip():
    print("Fatal Error: All models completely failed to generate any response.")
    sys.exit(1)

print("Processing output and generating HTML...")
html_content = markdown.markdown(
    answer_markdown, 
    extensions=['extra', 'codehilite', 'mdx_math'],
    extension_configs={'mdx_math': {'enable_dollar_delimiter': True}}
)

# Extract title from target filename
display_title = target_filename.replace('.pdf', '')

# Build final webpage structure with font-size: 22px
html_page = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Correction - {display_title}</title>

    <!-- Configure MathJax v2.7.7 for robust compatibility with mdx_math -->
    <script type="text/x-mathjax-config">
        MathJax.Hub.Config({{
            tex2jax: {{
                inlineMath: [['$','$'], ['\\(','\\)']],
                displayMath: [['$$','$$'], ['\\[','\\]']]
            }}
        }});
    </script>
    <script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>
    <script async src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.7/MathJax.js?config=TeX-MML-AM_CHTML"></script>

    <!-- Use Google Fonts for better aesthetics -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Outfit:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #FFE600;
            --text-color: #000000;
            --accent-color: #000000;
            --surface-color: #FFE600;
        }}
        body {{
            margin: 0;
            padding: 0;
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'Inter', sans-serif;
            font-size: 32px; /* VERY LARGE FONT AS REQUESTED */
            line-height: 1.6;
        }}
        .container {{
            width: 100%;
            min-height: 100vh;
            box-sizing: border-box;
            background: var(--surface-color);
            padding: 3rem 4rem 5rem;
        }}
        h1, h2, h3 {{
            font-family: 'Outfit', sans-serif;
            color: var(--accent-color);
        }}
        pre {{
            background: #ffe066;
            border: 2px solid #000;
            padding: 1rem;
            border-radius: 8px;
            overflow-x: auto;
        }}
        code {{
            font-family: monospace;
            background: #ffe066;
            border: 1px solid #000;
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Correction de l'examen {display_title}</h1>
        <hr style="border: 0; border-top: 2px solid #000; margin-bottom: 2rem;">
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
