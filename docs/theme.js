try { const t = localStorage.getItem("deid-theme"); if (t) document.documentElement.dataset.theme = t; } catch (e) {}
