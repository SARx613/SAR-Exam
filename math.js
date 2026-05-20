// ==UserScript==
// @name        AutoScroll Va-et-Vient + Reload
// @match       https://sarx613.github.io/SAR-Exam/*
// ==/UserScript==

// Variables globales
let currentPos = 0;
let direction = 1;
let pausing = false;
let timer = null;

// ─── Détection des exercices sur la page ────────────────────────────────────
function findExercicePosition(num) {
    const patterns = [
        `exercice ${num}`,
        `exercise ${num}`,
        `exo ${num}`,
        `exo. ${num}`,
        `exercice n°${num}`,
        `problème ${num}`,
        `probleme ${num}`,
        `partie ${num}`,
    ];

    const selectors = ['h1', 'h2', 'h3', 'h4', 'h5', 'b', 'strong', 'p', 'div'];

    for (const selector of selectors) {
        const elements = document.querySelectorAll(selector);
        for (const el of elements) {
            const text = el.textContent.trim().toLowerCase();
            for (const pattern of patterns) {
                if (text.startsWith(pattern) || text.includes(pattern)) {
                    const rect = el.getBoundingClientRect();
                    return rect.top + window.scrollY - 20; // 20px de marge au-dessus
                }
            }
        }
    }
    return null;
}

// ─── Saut vers un exercice ───────────────────────────────────────────────────
function jumpToExercice(num) {
    const pos = findExercicePosition(num);
    if (pos !== null) {
        currentPos = Math.max(0, pos);
        direction = 1;
        pausing = false;
        window.scrollTo(0, currentPos);
        console.log(`[AutoScroll] ✅ Saut vers Exercice ${num} — position ${Math.round(currentPos)}px`);
    } else {
        console.warn(`[AutoScroll] ⚠️ Exercice ${num} introuvable sur la page`);
    }
}

// ─── Détection du paramètre ?exo=N dans l'URL ───────────────────────────────
// Utilisé quand on arrive depuis les pages /1, /2, ..., /6
function getExoFromURL() {
    const params = new URLSearchParams(window.location.search);
    const exo = parseInt(params.get('exo'));
    return (!isNaN(exo) && exo >= 1 && exo <= 9) ? exo : null;
}

// ─── Boucle de défilement ───────────────────────────────────────────────────
function autoScrollLoop() {
    const speedDown = 0.15;  // descente lente
    const speedUp   = 20;    // remontée rapide

    if (timer) clearInterval(timer);

    timer = setInterval(() => {
        if (pausing) return;

        const limit = document.body.scrollHeight - window.innerHeight;

        if (direction === 1) {
            currentPos += speedDown;
        } else {
            currentPos -= speedUp;
        }

        window.scrollTo(0, currentPos);

        // Arrivé en bas → pause 6s puis remontée
        if (currentPos >= limit && direction === 1) {
            pausing = true;
            setTimeout(() => {
                direction = -1;
                pausing = false;
            }, 6000);
        }

        // Arrivé en haut → reload + restart (repart depuis 0 ou depuis l'exo de départ)
        if (currentPos <= 0 && direction === -1) {
            clearInterval(timer);
            location.reload();
        }

    }, 10);
}

// ─── Démarrage ───────────────────────────────────────────────────────────────
setTimeout(() => {
    const exoNum = getExoFromURL();
    if (exoNum !== null) {
        // Page /1 à /6 : on saute d'abord à l'exercice, puis on lance le scroll
        jumpToExercice(exoNum);
    }
    // Dans tous les cas, on démarre la boucle de scroll depuis currentPos
    autoScrollLoop();
}, 3000);