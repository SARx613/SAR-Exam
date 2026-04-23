# Maths Exam Correction via Groq and Google Drive

Ce projet est un script automatisé pour télécharger `"Algebre Exam 2026.pdf"` depuis votre **Google Drive**, utiliser l'intelligence artificielle Groq (Llama 3 70B) pour répondre à toutes les questions de niveau Universitaire (L3 Maths), et publier le résultat sur une jolie page web via **GitHub Pages**.

## 🚀 Étape 1 : Créer votre Google Service Account (Sans blocage 2FA !)

Puisque Google permet de créer des comptes "Robots" sans authentification bloquante, la connexion est extrêmement simple et fiable :

1. Allez sur la [Console Google Cloud](https://console.cloud.google.com/).
2. Créez un nouveau projet (ou sélectionnez-en un existant).
3. Cliquez sur **Menu (hamburger)** > **APIs & Services** > **Library**, cherchez **Google Drive API** et cliquez sur "Enable" (Activer).
4. Cliquez sur **Menu** > **IAM & Admin** > **Service Accounts**.
5. Cliquez sur "CREATE SERVICE ACCOUNT". Donnez-lui un nom (ex: `github-actions-bot`) et terminez la création.
6. **Le plus important :** Sur la page du Service Account que vous venez de créer, cliquez sur l'onglet **KEYS**, puis "ADD KEY" > "Create new key" au format **JSON**. 
   *Un fichier contenant plein de code sera téléchargé sur votre ordinateur.*

## ⚙️ Étape 2 : Configurer Google Drive et GitHub Secrets

### A. Dans Google Drive :
1. Copiez l'adresse email de votre "Service Account" (elle ressemble à `votre-nom@projetxyz.iam.gserviceaccount.com`).
2. Ouvrez votre dossier Google Drive où se trouve le fichier `Algebre Exam 2026.pdf`.
3. Cliquez-droit sur le fichier (ou le dossier) > **Partager**, et invitez l'adresse email de votre Service Account avec la permission **Lecteur** (Viewer). *(De cette façon, l'intelligence artificielle y a accès)*.

### B. Dans GitHub :
Sur la page de votre projet (GitHub.com) :
1. Allez dans **Settings** > **Secrets and variables** > **Actions**
2. Créez "New repository secret" pour chacune des valeurs suivantes :

- `GOOGLE_CREDENTIALS` : Ouvrez le fichier JSON que Google vous a donné à l'étape 1 avec n'importe quel éditeur de texte, et **collez TOUT son contenu ici**.
- `GROQ_API_KEY` : Votre clé secrète Groq.

## 🌐 Étape 3 : Activer GitHub Pages et Pousser le Code

1. Poussez ce dossier sur votre projet GitHub (`git init`, `git add .`, ...).
2. Sur la page du Repo GitHub, allez dans **Settings** > **Pages**.
3. Dans **Build and deployment**, sous "Source", selectionnez `Deploy from a branch`. 
4. Sous "Branch", selectionnez `main`, et pour le dossier, selectionnez `/docs`. Appuyez sur "Save".
5. Déclenchez l'action manuellement depuis l'onglet `Actions` (workflow dispatch), ou attendez qu'elle s'exécute d'elle-même (tous les jours à 8h du matin).

La page web sera alors disponible au lien standard fourni par GitHub Pages. L'output sera écrit en très gros (22px) pour bien le voir !
