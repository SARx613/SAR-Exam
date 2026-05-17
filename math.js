// ==UserScript==
// @name        AutoScroll Va-et-Vient + Reload
// @match       https://sarx613.github.io/SAR-Exam/*
// ==/UserScript==

function autoScrollLoop() {
    let speedDown = 0.5;   // descente lente
    let speedUp = 20;     // remontée plus rapide

    let direction = 1; // 1 = descendre, -1 = monter
    let currentPos = 0;
    let pausing = false;   // true pendant la pause de 6s en bas

    let timer = setInterval(() => {
        if (pausing) return;

        let limit = document.body.scrollHeight - window.innerHeight;

        if (direction === 1) {
            currentPos += speedDown;
        } else {
            currentPos -= speedUp;
        }

        window.scrollTo(0, currentPos);

        // Arrivé en bas → pause 6 secondes puis on remonte
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

// Lance après 3 secondes
setTimeout(autoScrollLoop, 3000);