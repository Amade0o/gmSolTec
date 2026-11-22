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
  // La pregunta puede repetir lo que se escribió: {nombre} se cambia por el valor del campo
  // "nombre" del formulario (de un desplegable, el texto elegido; de un campo "monto", en pesos).
  // Ej.: data-confirmar="¿Cargar {monto} como saldo inicial de {caja}?"
  function completarPregunta(pregunta, form) {
    return pregunta.replace(/\{(\w+)\}/g, function (todo, nombre) {
      var campo = form.elements[nombre];
      if (!campo) return todo;
      if (campo.tagName === "SELECT") return campo.selectedIndex >= 0 ? campo.options[campo.selectedIndex].text : "";
      if (nombre.indexOf("monto") === 0) {
        var numero = Number(campo.value);
        return isFinite(numero) && campo.value !== ""
          ? "$ " + numero.toLocaleString("es-AR", { maximumFractionDigits: 2 }) : "(sin monto)";
      }
      return campo.value;
    });
  }

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
      texto.textContent = completarPregunta(pregunta, form);
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

  // ---------- Imprimir ----------
  // En la orden, "Imprimir ▾" abre un menú (popover) con dos opciones: data-imprimir="orden" o
  // "comprobante". La opción elegida queda en <html data-imprimir="…"> y el CSS de impresión
  // muestra solo esa parte. En la venta hay un solo botón (data-imprimir vacío: la página).
  document.querySelectorAll("[data-imprimir], [data-menu-imprimir]").forEach(function (boton) { boton.hidden = false; });
  document.querySelectorAll("[data-imprimir]").forEach(function (boton) {
    boton.addEventListener("click", function () {
      var menu = boton.closest("[popover]");
      if (menu && menu.hidePopover) menu.hidePopover();
      document.documentElement.dataset.imprimir = boton.dataset.imprimir || "pagina";
      window.print();
    });
  });
  window.addEventListener("afterprint", function () { delete document.documentElement.dataset.imprimir; });
  // El menú se ubica debajo del botón con CSS (position-area). Donde el navegador todavía no lo
  // entiende (Firefox, por ejemplo), aparecía en cualquier lado: acá se lo ubica a mano.
  var menuImprimir = document.getElementById("menu-imprimir");
  if (menuImprimir && !(window.CSS && CSS.supports("position-area", "bottom span-left"))) {
    var botonMenu = document.querySelector("[popovertarget='menu-imprimir']");
    menuImprimir.addEventListener("toggle", function (e) {
      if (e.newState !== "open" || !botonMenu) return;
      var r = botonMenu.getBoundingClientRect();
      menuImprimir.style.position = "fixed";
      menuImprimir.style.top = r.bottom + "px";           // el CSS ya le da 6px de margen arriba
      menuImprimir.style.left = Math.max(8, r.right - menuImprimir.offsetWidth) + "px";
    });
    // Ubicado a mano no acompaña al botón si se desliza la página: se cierra
    window.addEventListener("scroll", function () {
      if (menuImprimir.matches(":popover-open")) menuImprimir.hidePopover();
    }, { passive: true });
  }

  // ---------- Buscador de clientes (Nueva orden, Venta rápida) ----------
  // Lo que se escribe acá busca clientes (HTMX); no tiene que recalcular el
  // resumen de la orden ni enviar el formulario con Enter.
  document.querySelectorAll("[data-buscar-cliente]").forEach(function (campo) {
    campo.addEventListener("input", function (e) { e.stopPropagation(); });
    campo.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.isComposing) e.preventDefault();
    });
  });
  // Otros campos que no recalculan el resumen (cliente nuevo) o que no envían con Enter
  document.querySelectorAll("[data-no-resumen]").forEach(function (campo) {
    campo.addEventListener("input", function (e) { e.stopPropagation(); });
  });
  document.querySelectorAll("[data-sin-enter]").forEach(function (campo) {
    campo.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.isComposing) e.preventDefault();
    });
  });

  // "Usar este" en el aviso de cliente parecido: pasa a "De la lista" con ese cliente elegido
  document.addEventListener("click", function (e) {
    var boton = e.target.closest("[data-usar-cliente]");
    if (!boton || !window.htmx) return;
    var deLaLista = document.querySelector("input[name='cli-modo'][value='existente']");
    var buscador = document.getElementById("buscar-cli-cliente");
    if (!deLaLista || !buscador) return;
    deLaLista.checked = true;
    buscador.value = "";
    htmx.ajax("GET", buscador.getAttribute("hx-get"), {
      target: "#opciones-cli-cliente", swap: "outerHTML",
      values: { campo: "cli-cliente", "cli-cliente": boton.dataset.usarCliente },
    }).then(function () { buscador.focus(); });
  });

  // ---------- Listas de filas (reparaciones, productos, pagos) ----------
  // Se muestra una fila; "+ Agregar otra" copia la fila vacía (<template>) y suma 1 al total
  // de filas que espera Django. "Quitar" saca la fila: Django ignora los números que faltan.
  function agregarFila(formset) {
    var total = formset.querySelector("input[name$='-TOTAL_FORMS']");
    var n = Number(total.value);
    var html = formset.querySelector("template[data-fila-vacia]").innerHTML
      .replace(/__prefix__/g, n).replace(/__num__/g, n + 1);
    var cuerpo = formset.querySelector("tbody");
    cuerpo.insertAdjacentHTML("beforeend", html);
    total.value = n + 1;
    var fila = cuerpo.lastElementChild;
    mejorar(fila);
    recalcular(formset.closest("form"));
    return fila;
  }

  document.addEventListener("click", function (e) {
    var agregar = e.target.closest("[data-agregar-fila]");
    if (agregar) {
      var fila = agregarFila(agregar.closest("[data-formset]"));
      var primero = fila.querySelector("select, input:not([hidden])");
      if (primero) primero.focus();
      return;
    }
    var quitar = e.target.closest("[data-quitar-fila]");
    if (quitar) {
      var formset = quitar.closest("[data-formset]");
      var form = quitar.closest("form");
      quitar.closest("tr").remove();
      formset.querySelector("[data-agregar-fila]").focus();
      recalcular(form);
      // el resumen de la derecha (HTMX) se recalcula con el formulario sin esa fila
      form.dispatchEvent(new Event("input", { bubbles: true }));
    }
  });

  // ---------- Precio y monto "automáticos" con lápiz ----------
  // Un campo con data-por-defecto se muestra como texto ($ 2.500) con un lápiz para cambiarlo.
  // Vacío = automático: "precio" es el de lista del producto elegido; "resto" es lo que falta
  // pagar de la venta; "recargo" es el del método de pago elegido. El servidor hace la misma
  // cuenta al guardar.
  var formato = new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 });
  var usoIconos = document.querySelector("use[href*='iconos.svg']");
  var sprite = usoIconos ? usoIconos.getAttribute("href").split("#")[0] : "";

  function prepararLapiz(campo) {
    if (campo.dataset.lapiz) return;
    campo.dataset.lapiz = "1";
    var etiqueta = campo.id && document.querySelector("label[for='" + campo.id + "']");
    var nombre = etiqueta ? etiqueta.textContent.replace(/,? fila.*$/, "") : "valor";
    // Todo el recuadro es un botón: se toca en cualquier parte (el número o el lápiz) para escribir
    var caja = document.createElement("button");
    caja.type = "button";
    caja.className = "por-defecto";
    // Armado con textContent (y no innerHTML): el texto de la etiqueta nunca se interpreta como HTML
    var oculto = document.createElement("span");
    oculto.className = "oculto";
    oculto.textContent = "Cambiar " + nombre.toLowerCase() + ": ";
    var valor = document.createElement("span");
    valor.className = "valor";
    var lapiz = document.createElement("span");
    lapiz.className = "lapiz";
    lapiz.setAttribute("aria-hidden", "true");
    lapiz.innerHTML = '<svg><use href="' + encodeURI(sprite) + '#i-lapiz"/></svg>';   // ruta propia, sin datos del usuario
    caja.append(oculto, valor, lapiz);
    campo.after(caja);
    caja.addEventListener("click", function () {
      campo.hidden = false;
      caja.hidden = true;
      if (campo.value === "" && caja.dataset.numero) campo.value = caja.dataset.numero;
      campo.focus();
      campo.select();
      campo.dispatchEvent(new Event("input", { bubbles: true }));
    });
    campo.addEventListener("blur", function () {
      if (campo.value === "") {             // vacío: vuelve a ser automático
        campo.hidden = true;
        caja.hidden = false;
        recalcular(campo.form);
      }
    });
    var conError = campo.closest(".con-error");
    campo.hidden = campo.value === "" && !conError;
    caja.hidden = !campo.hidden;
  }

  function mostrar(campo, numero, siNoHay, esPorcentaje) {
    var caja = campo.nextElementSibling;
    if (!caja || !caja.classList.contains("por-defecto")) return;
    caja.dataset.numero = numero == null ? "" : String(numero);
    caja.querySelector(".valor").textContent = numero == null ? siNoHay
      : esPorcentaje ? formato.format(numero) + " %" : "$ " + formato.format(numero);
  }

  // La fila del campo: en una tabla es su <tr>; si no, su fila de campos o el formulario
  function filaDe(campo) {
    return campo.closest("tr") || campo.closest(".fila-campos") || campo.form;
  }

  function recalcular(form) {
    if (!form) return;
    // Precio de lista del producto elegido en la misma fila
    form.querySelectorAll("input[data-por-defecto='precio']").forEach(function (campo) {
      var lista = filaDe(campo).querySelector("select[data-con-precio]");
      var opcion = lista && lista.selectedOptions[0];
      mostrar(campo, opcion && opcion.dataset.precio ? Number(opcion.dataset.precio) : null, "Elegí el producto");
    });
    // Recargo del método de pago elegido en la misma fila
    form.querySelectorAll("input[data-por-defecto='recargo']").forEach(function (campo) {
      var lista = filaDe(campo).querySelector("select[data-con-recargo]");
      var opcion = lista && lista.selectedOptions[0];
      mostrar(campo, opcion && opcion.dataset.recargo ? Number(opcion.dataset.recargo) : null, "Elegí el método", true);
    });
    // Lo que falta pagar: total de los productos menos los montos escritos (solo la venta rápida)
    var pagos = Array.prototype.slice.call(form.querySelectorAll("input[data-por-defecto='resto']"));
    if (!pagos.length) return;
    var total = 0;
    form.querySelectorAll("select[data-con-precio]").forEach(function (lista) {
      var opcion = lista.selectedOptions[0];
      if (!opcion || !opcion.dataset.precio) return;
      var fila = lista.closest("tr");
      var cantidad = Number((fila.querySelector("input[name$='cantidad_adquirida']") || {}).value) || 1;
      var precio = fila.querySelector("input[data-por-defecto='precio']");
      total += cantidad * (precio && precio.value !== "" ? Number(precio.value) : Number(opcion.dataset.precio));
    });
    var escrito = pagos.reduce(function (suma, p) { return suma + (p.value !== "" ? Number(p.value) : 0); }, 0);
    var primero = true;
    pagos.forEach(function (p) {
      if (p.value !== "") return;
      mostrar(p, primero ? Math.max(total - escrito, 0) : null, "Escribí el monto");
      primero = false;
    });
  }

  function mejorar(raiz) {
    raiz.querySelectorAll("input[data-por-defecto]").forEach(prepararLapiz);
    raiz.querySelectorAll("[data-quitar-fila], [data-agregar-fila]").forEach(function (b) { b.hidden = false; });
  }

  // Al elegir un producto, la cantidad se completa con 1 (casi siempre es 1; se puede cambiar)
  document.addEventListener("change", function (e) {
    if (!e.target.matches("select[data-con-precio]") || !e.target.value) return;
    var cantidad = filaDe(e.target).querySelector("input[name$='cantidad_adquirida']");
    if (cantidad && cantidad.value === "") {
      cantidad.value = "1";
      cantidad.dispatchEvent(new Event("input", { bubbles: true }));
    }
  });

  // Alta rápida de modelo o reparación: marca/categoría de la lista O escrita nueva, en el mismo lugar
  document.addEventListener("click", function (e) {
    var escribir = e.target.closest("[data-escribir-nuevo]");
    var elegir = e.target.closest("[data-elegir-lista]");
    if (!escribir && !elegir) return;
    var form = (escribir || elegir).closest("form");
    var deLista = form.querySelector("[data-elegir-padre]");
    var nuevo = form.querySelector("[data-escribir-padre]");
    deLista.hidden = !!escribir;
    nuevo.hidden = !escribir;
    if (escribir) {
      deLista.querySelector("select").value = "";
      nuevo.querySelector("input").focus();
    } else {
      nuevo.querySelector("input").value = "";
      deLista.querySelector("select").focus();
    }
  });

  mejorar(document);
  document.querySelectorAll("form").forEach(recalcular);
  document.addEventListener("input", function (e) { recalcular(e.target.form); });
  document.addEventListener("change", function (e) { recalcular(e.target.form); });

  // ---------- "+ Nuevo" del catálogo (marca, categoría, modelo, reparación) ----------
  // El botón pide el formulario con HTMX y lo pone en el diálogo; al guardar, el servidor
  // avisa con el evento "catalogo-agregado" y la opción nueva queda elegida.
  var altaRapida = document.getElementById("alta-rapida");
  var cuerpoAlta = document.getElementById("alta-rapida-cuerpo");
  if (altaRapida && cuerpoAlta) {
    document.body.addEventListener("htmx:afterSwap", function (e) {
      if (e.detail.target !== cuerpoAlta || cuerpoAlta.querySelector("[data-listo]")) return;
      if (!altaRapida.open) altaRapida.showModal();
      var primero = cuerpoAlta.querySelector(".con-error input, .con-error select, input:not([type=hidden]), select");
      if (primero) primero.focus();
    });
    altaRapida.addEventListener("click", function (e) {
      if (e.target.closest("[data-cerrar-dialogo]")) altaRapida.close();
    });
    altaRapida.addEventListener("close", function () { cuerpoAlta.innerHTML = ""; });

    document.body.addEventListener("catalogo-agregado", function (e) {
      var d = e.detail;
      var selector = "select[data-catalogo='" + d.seccion + "']";
      // la opción nueva va en todos los desplegables de ese tipo (y en las filas por agregar)
      var listas = Array.prototype.slice.call(document.querySelectorAll(selector));
      document.querySelectorAll("template[data-fila-vacia]").forEach(function (t) {
        listas = listas.concat(Array.prototype.slice.call(t.content.querySelectorAll(selector)));
      });
      listas.forEach(function (lista) { lista.add(new Option(d.texto, d.id)); });
      var destino = null;
      if (String(d.destino).indexOf("formset-") === 0) {
        var formset = document.querySelector("[data-formset='" + d.destino.slice(8) + "']");
        if (formset) {
          destino = Array.prototype.slice.call(formset.querySelectorAll("tbody " + selector))
            .filter(function (l) { return !l.value; })[0];
          if (!destino) destino = agregarFila(formset).querySelector(selector);
        }
      } else if (d.destino) {
        destino = document.getElementById(d.destino);
      }
      if (destino) {
        destino.value = String(d.id);
        destino.dispatchEvent(new Event("change", { bubbles: true }));
        destino.dispatchEvent(new Event("input", { bubbles: true }));
      }
      altaRapida.close();
      if (destino) destino.focus();
      if (document.ariaNotify) document.ariaNotify("Se agregó " + d.texto);
    });
  }
})();
