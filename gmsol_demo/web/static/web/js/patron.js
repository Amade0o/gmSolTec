// Patrón de bloqueo: grilla de 9 puntos.
// Se tocan los puntos en orden y se guarda en el campo "Clave" como "1-5-9-6".
// También muestra u oculta el campo "Clave" según el tipo de bloqueo.
// Sin este archivo la pantalla funciona igual: la clave se escribe a mano.
(() => {
  const patron = document.querySelector("[data-patron]");
  const opciones = document.querySelector("[data-bloqueo]");
  if (!patron || !opciones) return;

  const clave = document.getElementById(patron.dataset.patron);
  const campoClave = clave.closest(".campo");
  const linea = patron.querySelector("polyline");
  const puntos = patron.querySelectorAll("[data-punto]");
  let secuencia = [];

  // Centro de cada punto dentro del dibujo (grilla de 3x3 en 150x150)
  const centro = (numero) => {
    const i = numero - 1;
    return `${25 + (i % 3) * 50},${25 + Math.floor(i / 3) * 50}`;
  };

  function dibujar() {
    for (const b of puntos) {
      const orden = secuencia.indexOf(b.dataset.punto);
      // aria-pressed dice si el punto está marcado; el nombre dice en qué orden
      b.setAttribute("aria-pressed", orden !== -1);
      b.setAttribute("aria-label", orden === -1 ? `Punto ${b.dataset.punto}` : `Punto ${b.dataset.punto}, paso ${orden + 1}`);
    }
    linea.setAttribute("points", secuencia.map(centro).join(" "));
    clave.value = secuencia.join("-");
    clave.dispatchEvent(new Event("input", { bubbles: true }));
  }

  // Si ya había un patrón cargado (por ejemplo, después de un error), se dibuja
  function leerClave() {
    secuencia = /^[1-9](-[1-9])+$/.test(clave.value) ? clave.value.split("-") : [];
    dibujar();
  }

  function segunTipo() {
    const tipo = opciones.querySelector("input:checked")?.value ?? "ninguno";
    patron.hidden = tipo !== "patron";
    campoClave.hidden = tipo === "ninguno";
    if (tipo === "ninguno") clave.value = "";
    clave.readOnly = tipo === "patron";
    if (tipo === "patron") leerClave();
  }

  for (const b of puntos) {
    b.addEventListener("click", () => {
      if (!secuencia.includes(b.dataset.punto)) {
        secuencia.push(b.dataset.punto);
        dibujar();
      }
    });
  }
  patron.querySelector("[data-borrar]").addEventListener("click", () => {
    secuencia = [];
    dibujar();
  });
  opciones.addEventListener("change", () => {
    clave.value = "";       // al cambiar de tipo, la clave anterior ya no sirve
    segunTipo();
  });
  segunTipo();
})();
