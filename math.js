// ==UserScript==
// @name        AutoScroll Va-et-Vient + Reload
// @match       https://sarx613.github.io/SAR-Exam/*
// ==/UserScript==

// Variables globales accessibles par tout le script
let currentPos = 0;
let direction = 1;
let pausing = false;
let timer = null;

// ─── Recherche de la position d'un exercice dans la page ────────────────────
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

    // Cherche d'abord dans les titres (priorité) puis dans le reste
    const selectors = ['h1', 'h2', 'h3', 'h4', 'h5', 'b', 'strong', 'p'];

    for (const selector of selectors) {
        for (const el of document.querySelectorAll(selector)) {
            const text = el.textContent.trim().toLowerCase();
            for (const pattern of patterns) {
                if (text.startsWith(pattern) || text.includes(pattern)) {
                    const rect = el.getBoundingClientRect();
                    return Math.max(0, rect.top + window.scrollY - 30); // 30px de marge
                }
            }
        }
    }
    return null; // Non trouvé
}

// ─── Saut vers un exercice ───────────────────────────────────────────────────
function jumpToExercice(num) {
    const pos = findExercicePosition(num);
    if (pos !== null) {
        currentPos = pos;
        direction = 1;
        pausing = false;
        window.scrollTo(0, currentPos);
        console.log(`[AutoScroll] ✅ Exercice ${num} trouvé → position ${Math.round(currentPos)}px`);
    } else {
        console.warn(`[AutoScroll] ⚠️ Exercice ${num} introuvable sur la page — départ depuis le début`);
        currentPos = 0;
    }
}

// ─── Boucle principale de défilement ────────────────────────────────────────
function autoScrollLoop() {
    const speedDown = 0.15;  // descente lente (px par tick de 10ms = 15px/s)
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

        // Arrivé en haut → reload + restart
        if (currentPos <= 0 && direction === -1) {
            clearInterval(timer);
            location.reload();
        }

    }, 10);
}

// ─── Point d'entrée ──────────────────────────────────────────────────────────
// Vérifie si on arrive depuis une sous-page /1 à /6
const startExo = sessionStorage.getItem('startExercice');

if (startExo) {
    // Nettoie le flag immédiatement
    sessionStorage.removeItem('startExercice');
    const num = parseInt(startExo);
    console.log(`[AutoScroll] 🎯 Mode exercice ${num} détecté`);

    // Attend que la page et MathJax soient rendus avant de sauter
    function startFromExercice() {
        setTimeout(() => {
            jumpToExercice(num);
            // Lance le scroll 1s après le saut (laisse MathJax finir)
            setTimeout(autoScrollLoop, 1000);
        }, 800);
    }

    if (document.readyState === 'complete') {
        startFromExercice();
    } else {
        window.addEventListener('load', startFromExercice);
    }

} else {
    // Démarrage normal depuis le haut après 3 secondes
    setTimeout(autoScrollLoop, 3000);
}