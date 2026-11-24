# Agente: grafo LangGraph

El Data Agent responde cada pregunta recorriendo un grafo de estados de LangGraph
([`apps/api/src/app/agent/graph.py`](../apps/api/src/app/agent/graph.py)). El
modelo decide qué herramientas tipadas llama; el grafo fija el orden, los
límites y las comprobaciones. El modelo nunca escribe SQL ni ve Gold directamente:
solo recibe los resultados compactos de las herramientas.

```mermaid
graph TD;
	__start__([inicio]) --> contexto;
	contexto --> modelo;
	modelo -.-> herramientas;
	herramientas --> modelo;
	modelo -.-> verificar;
	verificar -.-> modelo;
	verificar -.-> componer;
	componer --> __end__([fin]);
```

Las flechas discontinuas son decisiones. El diagrama se genera con
`build_graph(...).get_graph().draw_mermaid()` y una prueba comprueba que estas
aristas coinciden con las del grafo compilado.

## Estado

| Campo | Contenido |
| --- | --- |
| `question`, `model`, `account` | Pregunta, modelo elegido y cuenta que paga la inferencia |
| `history` | Turnos anteriores de la conversación, con su evidencia verificada |
| `area` | Área dibujada en un mapa, si está activa (polígono `[lng, lat]`) |
| `inputs` | Mensajes y llamadas que se envían al modelo en cada vuelta |
| `calls` | Herramientas pedidas por el modelo en la última vuelta |
| `visuals` | Resultados completos de Gold; cada uno es una visualización |
| `trace` | Cada herramienta llamada, con sus argumentos o su error |
| `rounds`, `rewrites` | Vueltas del modelo y reescrituras hechas |
| `turn` | El turno final que devuelve y guarda la API |

## Nodos

1. **contexto.** Construye las instrucciones con el catálogo de Gold, los
   últimos 12 turnos con su evidencia verificada (para las preguntas de
   seguimiento) y, si hay un área activa, la nota que la explica.
2. **modelo.** Una llamada a Responses. Si el modelo pide herramientas, pasa a
   *herramientas*; si responde con texto, pasa a *verificar*. Tras 10 vueltas
   corta con un error 422 que pide concretar la pregunta.
3. **herramientas.** Ejecuta `search_certified`, `run_certified`, `query_gold`,
   `find_entities` y `describe_data` sobre Gold. Un error del contrato vuelve al
   modelo con su código para que corrija los argumentos. Con un área activa, la
   API la añade a cada `query_gold`.
4. **verificar.** Comprobaciones deterministas sobre la respuesta: que haya
   texto legible y que dé una sola cifra, sin rangos de informes (regla de
   [PRODUCT.md](../PRODUCT.md)). Si falla, pide una reescritura sin nuevas
   herramientas; a la segunda acepta la respuesta para no entrar en un bucle.
5. **componer.** Arma el turno: respuesta, visualizaciones, traza, carga Gold y
   `visualization_action`.

## Continuidad entre turnos

- `visualization_action` es `create` cuando el turno trae resultados nuevos y
  `retain` cuando no (una aclaración o un comentario). Con `retain`, la web
  sigue mostrando los resultados anteriores, como en el contrato del agente de
  Messi.
- El área seleccionada en un mapa limita todas las preguntas siguientes hasta
  que se quita.
- Cada turno guarda sus consultas; el siguiente las recibe como evidencia para
  modificar solo lo que pide la pregunta.

## Diferencia con el agente de Messi

El repositorio de Messi incluye un grafo LangGraph determinista de tres nodos
(resolver, consultar, componer) que entiende un vocabulario fijo, pero su API
responde con un bucle de herramientas sin grafo. Aquí el grafo es el que
atiende cada pregunta: conserva la flexibilidad del modelo y añade nodos
explícitos de contexto y verificación.

## Pruebas

`apps/api/tests/test_runtime.py` recorre el grafo con un modelo simulado:
respuesta directa, consulta certificada, reparación de errores, límite de
vueltas, reescritura de un rango y `visualization_action`.
