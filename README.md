# 🎓 Correcteur Automatique d'Examen Universitaire (IA + Google Drive + GitHub Pages)

Ce projet est un pipeline entièrement automatisé qui :

1. **Télécharge un PDF d'examen** depuis votre Google Drive.
2. **Extrait le texte** du PDF avec PyMuPDF.
3. **Génère une correction complète et rigoureuse** de niveau universitaire (L3) à l'aide d'un modèle d'IA (Groq ou Claude d'Anthropic).
4. **Valide la complétude** de la correction grâce à un superviseur IA dédié, et force des itérations si la réponse est incomplète.
5. **Publie le résultat** sous forme de page HTML avec rendu LaTeX/MathJax sur **GitHub Pages**.

L'action GitHub se déclenche automatiquement **tous les jours à 8h du matin (heure Argentine)**, ou manuellement depuis l'onglet `Actions` de GitHub.

---

## 🤖 Modèles d'IA disponibles

Le provider est configurable via la variable d'environnement `MODEL_PROVIDER` :

| Valeur              | Modèle utilisé              | Coût approximatif       |
|---------------------|-----------------------------|-------------------------|
| `groq` (défaut)     | GPT-OSS-120B → Llama-70B    | Gratuit                 |
| `claude_haiku`      | Claude Haiku 4.5            | $1 / $5 par MTok        |
| `claude_sonnet`     | Claude Sonnet 4.6           | $3 / $15 par MTok       |
| `claude_opus`       | Claude Opus 4.7             | $5 / $25 par MTok       |

> **Fallback automatique :** Si Claude manque de crédits ou atteint une limite de taux, le script bascule automatiquement sur Groq.

---

## 🗂️ Choisir le fichier d'examen à corriger

Modifiez simplement le contenu du fichier **`exam_filename.txt`** à la racine du projet :

```
Algebre Exam 2026.pdf
```

Le script cherchera ce fichier par nom exact dans votre Google Drive.

---

## 🚀 Installation et Configuration

### Étape 1 : Créer un compte de service Google (Service Account)

1. Rendez-vous sur la [Console Google Cloud](https://console.cloud.google.com/).
2. Créez un nouveau projet ou sélectionnez un projet existant.
3. Dans le menu, allez dans **APIs & Services** > **Library**, cherchez **Google Drive API** et cliquez sur **Enable**.
4. Allez dans **IAM & Admin** > **Service Accounts**, puis cliquez sur **CREATE SERVICE ACCOUNT**.
5. Donnez-lui un nom (ex : `github-actions-bot`) et terminez la création.
6. Sur la page du Service Account créé, allez dans l'onglet **KEYS** > **ADD KEY** > **Create new key** (format **JSON**).
   *Un fichier JSON sera téléchargé sur votre ordinateur — ne le perdez pas.*

### Étape 2 : Partager le fichier PDF avec le Service Account

1. Copiez l'adresse email de votre Service Account (ex : `mon-bot@mon-projet.iam.gserviceaccount.com`).
2. Dans Google Drive, faites un clic droit sur votre fichier PDF d'examen > **Partager**.
3. Invitez l'adresse email du Service Account avec le rôle **Lecteur (Viewer)**.

### Étape 3 : Configurer les secrets GitHub

Sur la page de votre dépôt GitHub, allez dans **Settings** > **Secrets and variables** > **Actions**, puis créez les secrets suivants :

| Nom du secret        | Valeur                                                                 |
|----------------------|------------------------------------------------------------------------|
| `GOOGLE_CREDENTIALS` | Le contenu **entier** du fichier JSON téléchargé à l'étape 1.         |
| `GROQ_API_KEY`       | Votre clé API Groq (obtenue sur [console.groq.com](https://console.groq.com)). |
| `ANTHROPIC_API_KEY`  | *(Optionnel)* Votre clé API Anthropic si vous utilisez Claude.        |
| `MODEL_PROVIDER`     | *(Optionnel)* `groq`, `claude_haiku`, `claude_sonnet`, ou `claude_opus`. Par défaut : `groq`. |

### Étape 4 : Activer GitHub Pages

1. Dans les paramètres de votre dépôt GitHub (**Settings** > **Pages**).
2. Sous **Build and deployment**, sélectionnez **Deploy from a branch**.
3. Choisissez la branche `main` et le dossier `/docs`. Cliquez sur **Save**.

---

## ▶️ Utilisation

### Déclenchement automatique
L'action s'exécute automatiquement **tous les jours à 8h00 (heure Argentine, UTC-3)**.

### Déclenchement manuel
1. Allez dans l'onglet **Actions** de votre dépôt GitHub.
2. Sélectionnez le workflow dans la liste.
3. Cliquez sur **Run workflow**.

### Résultat
Une fois l'action terminée, la page HTML de correction est disponible à l'URL GitHub Pages de votre dépôt (ex : `https://votre-nom.github.io/votre-repo/`).

La page affiche la correction complète avec :
- Un rendu **MathJax** pour toutes les formules mathématiques LaTeX.
- Un style **dark mode** avec une police large (26px) pour une lecture confortable.

---

## 📁 Structure du projet

```
.
├── main.py               # Script principal du pipeline IA
├── exam_filename.txt     # Nom du fichier PDF à corriger dans Google Drive
├── requirements.txt      # Dépendances Python
├── docs/
│   └── index.html        # Page HTML générée (publiée sur GitHub Pages)
└── .github/
    └── workflows/        # Définition de l'action GitHub (CI/CD)
```

---

## 🔒 Sécurité

- Ne committez **jamais** le fichier JSON de votre Service Account dans le dépôt.
- Toutes les clés API doivent être stockées exclusivement dans les **GitHub Secrets**, pas dans le code.
- Le fichier `.gitignore` est configuré pour exclure les fichiers sensibles.
