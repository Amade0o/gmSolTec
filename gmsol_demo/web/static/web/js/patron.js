// Patrón de bloqueo: grilla de 9 puntos.
// Se tocan los puntos en orden y se guarda en el campo "Clave" como "1-5-9-6".
// También muestra u oculta el campo "Clave" según el tipo de bloqueo.
// Sin este archivo la pantalla funciona igual: la clave se escribe a mano.
(function () {
  var patron = document.querySelector("[data-patron]");
  var opciones = document.querySelector("[data-bloqueo]");
  if (!patron || !opciones) return;

  var clave = document.getElementById(patron.dataset.patron);
  var campoClave = clave.closest(".campo");
  var linea = patron.querySelector("polyline");
  var puntos = patron.querySelectorAll("[data-punto]");
  var secuencia = [];

  // Centro de cada punto dentro del dibujo (grilla de 3x3 en 150x150)
  function centro(numero) {
    var i = numero - 1;
    return (25 + (i % 3) * 50) + "," + (25 + Math.floor(i / 3) * 50);
  }

  function dibujar() {
    puntos.forEach(function (b) {
      b.classList.toggle("on", secuencia.indexOf(b.dataset.punto) !== -1);
    });
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
    var elegido = opciones.querySelector("input:checked");
    var tipo = elegido ? elegido.value : "ninguno";
    patron.hidden = tipo !== "patron";
    campoClave.hidden = tipo === "ninguno";
    if (tipo === "ninguno") clave.value = "";
    clave.readOnly = tipo === "patron";
    if (tipo === "patron") leerClave();
  }

  puntos.forEach(function (b) {
    b.addEventListener("click", function () {
      if (secuencia.indexOf(b.dataset.punto) === -1) {
        secuencia.push(b.dataset.punto);
        dibujar();
      }
    });
  });
  patron.querySelector("[data-borrar]").addEventListener("click", function () {
    secuencia = [];
    dibujar();
  });
  opciones.addEventListener("change", function () {
    clave.value = "";       // al cambiar de tipo, la clave anterior ya no sirve
    segunTipo();
  });
  segunTipo();
})();
