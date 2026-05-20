// ==UserScript==
// @name        AutoScroll Va-et-Vient + Reload
// @match       https://sarx613.github.io/SAR-Exam/*
// ==/UserScript==

let currentPos = 0;
let direction = 1;
let pausing = false;
let timer = null;

// ─── Lecture du paramètre ?exo=N dans l'URL ──────────────────────────────────
const exoParam = new URLSearchParams(location.search).get('exo');

// ─── Recherche d'un exercice dans la page ────────────────────────────────────
function findExercicePosition(num) {
    const patterns = [`exercice ${num}`, `exercise ${num}`, `exo ${num}`, `partie ${num}`, `problème ${num}`];
    for (const selector of ['h1', 'h2', 'h3', 'h4', 'strong', 'b']) {
        for (const el of document.querySelectorAll(selector)) {
            const text = el.textContent.trim().toLowerCase();
            if (patterns.some(p => text.startsWith(p) || text.includes(p))) {
                const pos = Math.max(0, el.getBoundingClientRect().top + window.scrollY - 30);
                console.log(`[AutoScroll] Exercice ${num} trouvé dans <${selector}> : "${el.textContent.trim()}" → ${Math.round(pos)}px`);
                return pos;
            }
        }
    }
    console.warn(`[AutoScroll] Exercice ${num} INTROUVABLE dans la page`);
    return null;
}

// ─── Boucle de défilement ────────────────────────────────────────────────────
function autoScrollLoop() {
    if (timer) clearInterval(timer);
    timer = setInterval(() => {
        if (pausing) return;
        const limit = document.body.scrollHeight - window.innerHeight;

        currentPos += (direction === 1) ? 0.15 : -20;
        window.scrollTo(0, currentPos);

        if (currentPos >= limit && direction === 1) {
            pausing = true;
            setTimeout(() => { direction = -1; pausing = false; }, 6000);
        }
        if (currentPos <= 0 && direction === -1) {
            clearInterval(timer);
            location.reload();
        }
    }, 10);
}

// ─── Démarrage ───────────────────────────────────────────────────────────────
if (exoParam) {
    // Le UserScript s'exécute après le chargement → on n'attend plus l'événement 'load'
    // On attend juste que MathJax ait fini de rendre les formules (~2s)
    console.log(`[AutoScroll] Paramètre exo=${exoParam} détecté, saut dans 2s…`);
    setTimeout(() => {
        const pos = findExercicePosition(parseInt(exoParam));
        if (pos !== null) {
            currentPos = pos;
            window.scrollTo(0, currentPos);
        }
        setTimeout(autoScrollLoop, 800);
    }, 2000);
} else {
    // Page normale → départ depuis le haut après 3s
    console.log('[AutoScroll] Démarrage normal depuis le haut');
    setTimeout(autoScrollLoop, 3000);
}