GMSol — Notas abiertas sobre el modelo BPMN

Complementa a BPMN.md. Acá van cosas que se discutieron pero no son planeación a futuro (eso ya está en tu archivo aparte) sino detalles del modelo actual que quedaron sin decisión final o que conviene tener presentes.

1. "Acordar método de pago" repetido: ¿Call Activity o subproceso propio?

El patrón "Acordar método de pago" aparece en tres puntos del diagrama:

Venta de producto directa.
Antes de reparar (con porcentaje de pago: total o seña).
Al retirar, si queda saldo pendiente.

Hoy está dibujado como subproceso colapsado normal en cada lugar. Si es el mismo proceso reutilizado, conviene modelarlo como Call Activity (como ya hiciste con "Solicitar producto ya"), para dejar explícito que las tres instancias comparten una sola definición y no son tres lógicas separadas que coinciden en nombre. Es una mejora de consistencia, no un error — está sin resolver.

2. Fusionar o no "Acordar método de pago" con "Crear factura"

Quedó como pregunta abierta en el camino de venta directa de producto (sección 3 del doc principal). Mi sugerencia fue mantenerlos separados, porque marca la frontera entre "negociación con el cliente" (puede implicar ida y vuelta) y "efecto interno del sistema" (impacta caja/stock). Falta que lo confirmes.

3. Flecha duplicada entre "Acordar método de pago" y "Crear factura"

Detectada en la última versión de la pizarra: una conexión roja bidireccional superpuesta con una negra de un solo sentido. Está anotada en el documento principal, pero repito acá porque es un ajuste físico en el dibujo, no solo conceptual — hay que borrar una de las dos líneas en la próxima pasada del diagrama.

4. Confirmado: "Solicitar producto ya" (como Call Activity) ya tiene su propio evento de fin

En la última foto se ve la call activity conectada a un círculo de fin (evento de fin simple). Esto ya no es una nota pendiente, es una confirmación: quedó bien resuelto, sin acción necesaria.

5. Gateways revisados y confirmados correctos

Durante el análisis de la pizarra hubo dudas sobre símbolos de gateway (exclusivo X vs. paralelo +) en la zona de accesorios y "¿hay stock?". Se confirmó que están bien marcados como exclusivos (X) donde corresponde — no quedó ningún error de notación pendiente en los gateways.

Si más adelante volvés a tocar el diagrama, lo más práctico es que actualicemos directamente BPMN.md en vez de ir acumulando notas sueltas como esta.