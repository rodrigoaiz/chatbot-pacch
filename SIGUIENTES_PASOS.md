# Siguientes pasos

## Objetivo

Mantener al Portal Academico del CCH como fuente de verdad. El modelo local debe
buscar, resumir y citar; nunca completar datos precisos que no aparezcan en las
fuentes recuperadas.

## Fase 1: seguridad de respuestas

- Cambiar la temperatura de generacion a `0`.
- Extraer evidencia antes de redactar la respuesta.
- Bloquear fechas y cantidades que no aparezcan en los fragmentos fuente.
- Rechazar la respuesta cuando no exista evidencia explicita.
- Agregar pruebas de regresion para preguntas factuales y preguntas sin respuesta.

Resultado esperado: el sistema prefiere indicar que no encontro el dato antes
que inventarlo.

## Fase 2: mejorar la recuperacion

- Recuperar entre 20 y 30 candidatos en lugar de seleccionar directamente tres.
- Reordenar los candidatos segun la intencion de la pregunta: fecha, persona,
  definicion, causa, etapa o cantidad.
- Enviar al modelo solamente los 5 a 8 fragmentos mejor sustentados.
- Favorecer coincidencias completas sobre coincidencias aisladas por tema.
- Evaluar `Recall@5` y `Recall@10` con preguntas reales del Portal.

Resultado esperado: preguntas como la fecha de inicio de la Independencia deben
recuperar las paginas `primeraEtapa` o `etapas`, donde aparece el dato exacto.

## Fase 3: respaldo en linea

- Consultar el Portal solo cuando la base local no tenga evidencia suficiente.
- Limitar la consulta a paginas candidatas del dominio oficial.
- Incorporar al indice el contenido nuevo o actualizado.
- Mantener limites de tiempo, pausas y una respuesta clara si el Portal no esta
  disponible.

Resultado esperado: conservar respuestas actuales sin depender de Internet para
cada consulta ni cargar innecesariamente el Portal.

## Fase 4: evaluacion y observabilidad

- Registrar pregunta, fragmentos seleccionados, respuesta y motivo de rechazo.
- Crear un conjunto de evaluacion por asignatura con datos exactos y preguntas
  fuera de alcance.
- Medir recuperacion, respuestas sustentadas, rechazos correctos y datos no
  respaldados.
- Revisar periodicamente los errores reales para ampliar las pruebas.

## Fase futura: escalar el modelo

Un modelo mayor puede mejorar la redaccion y el seguimiento de instrucciones,
pero no sustituye la recuperacion ni la validacion. Se evaluara al migrar a una
maquina o servicio con mas memoria y capacidad de computo.

## Orden recomendado

1. Validacion de fechas y cantidades.
2. Pruebas de regresion.
3. Recuperacion y reordenamiento de candidatos.
4. Respaldo en linea contra el Portal.
5. Evaluacion de infraestructura y modelos mayores.

## Criterio de salida

Una respuesta factual se publica solo si sus datos precisos aparecen en una
fuente del Portal mostrada al usuario. Si no hay evidencia, el sistema lo indica
sin usar el conocimiento interno del modelo como sustituto.
