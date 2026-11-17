// Mejoras de la interfaz que necesitan JavaScript.
// Todas son "extra": sin este archivo cada pantalla funciona igual,
// solo que sin confirmación, con los avisos arriba y sin botón Imprimir.
// Se carga con defer: corre cuando la página ya está armada.
(function () {
  "use strict";

  // ---------- Avisos ("Orden #12 creada.") flotando abajo a la derecha ----------
  // Sin JS se ven arriba del contenido, como siempre. Los de éxito se van solos
  // a los 6 segundos (si el mouse o el foco no están encima); los de error quedan.
  var avisos = document.getElementById("avisos");
  if (avisos && "showPopover" in HTMLElement.prototype) {
    avisos.popover = "manual";
    var quitar = function (aviso, automatico) {
      if (automatico && aviso.matches(":hover, :focus-within")) {
        setTimeout(function () { quitar(aviso, true); }, 2000);
        return;
      }
      var teniaFoco = aviso.contains(document.activeElement);
      aviso.remove();
      var siguiente = avisos.querySelector(".cerrar");
      if (!siguiente) avisos.hidePopover();
      if (teniaFoco) (siguiente || document.getElementById("contenido")).focus();
    };
    avisos.querySelectorAll(".aviso").forEach(function (aviso) {
      var cerrar = document.createElement("button");
      cerrar.type = "button";
      cerrar.className = "cerrar";
      cerrar.setAttribute("aria-label", "Cerrar aviso");
      cerrar.textContent = "×";
      cerrar.addEventListener("click", function () { quitar(aviso); });
      aviso.append(cerrar);
      if (!aviso.classList.contains("error")) {
        setTimeout(function () { quitar(aviso, true); }, 6000);
      }
    });
    avisos.showPopover();
    // Que el lector de pantalla también lo diga (donde el navegador lo permite)
    if (document.ariaNotify) document.ariaNotify(avisos.textContent.replace(/×/g, "").trim());
  }

  // ---------- Confirmar antes de quitar o desactivar ----------
  // Un botón (o formulario) con data-confirmar="¿Quitar…?" pide confirmación.
  // data-confirmar-si cambia el texto del botón que confirma.
  var dialogo = document.getElementById("confirmar");
  if (dialogo && dialogo.showModal) {
    var texto = document.getElementById("confirmar-texto");
    var botonSi = dialogo.querySelector("[value=si]");
    var pendiente = null;

    document.addEventListener("submit", function (e) {
      var form = e.target;
      var boton = e.submitter;
      var pregunta = (boton && boton.dataset.confirmar) || form.dataset.confirmar;
      if (!pregunta || form.dataset.confirmado) return;
      e.preventDefault();
      pendiente = { form: form, boton: boton };
      texto.textContent = pregunta;
      botonSi.textContent = (boton && boton.dataset.confirmarSi) || form.dataset.confirmarSi || "Sí, seguir";
      dialogo.returnValue = "";
      dialogo.showModal();
    });

    dialogo.addEventListener("close", function () {
      var elegido = dialogo.returnValue;
      dialogo.returnValue = "";
      if (elegido === "si" && pendiente) {
        pendiente.form.dataset.confirmado = "1";
        pendiente.form.requestSubmit(pendiente.boton || undefined);
        delete pendiente.form.dataset.confirmado;
      }
      pendiente = null;
    });
  }

  // ---------- Botón Imprimir (comprobante de orden o venta) ----------
  document.querySelectorAll("[data-imprimir]").forEach(function (boton) {
    boton.hidden = false;
    boton.addEventListener("click", function () { window.print(); });
  });

  // ---------- Buscador de clientes (Nueva orden, Venta rápida) ----------
  // Lo que se escribe acá busca clientes (HTMX); no tiene que recalcular el
  // resumen de la orden ni enviar el formulario con Enter.
  document.querySelectorAll("[data-buscar-cliente]").forEach(function (campo) {
    campo.addEventListener("input", function (e) { e.stopPropagation(); });
    campo.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.isComposing) e.preventDefault();
    });
  });
})();
