# Visualización de modelos 3D

**Estado · Implementada** en el Data Agent: visor de las 28 formas y estilo «Modelos» del mapa.

Visor WebGL de las 28 categorías de forma normalizada. Permite ver la cuadrícula completa, aislar una forma, girar, acercar y restablecer la vista.

## Utilidad para el Data Agent

Comparar de forma coherente los símbolos usados en el mapa, la ficha y una leyenda del Data Agent.

## Recursos originales

El archivo [visor-modelos.js](visor-modelos.js) es el visor original. [mapas-analiticos.js](../../_compartido/js/mapas-analiticos.js) define y genera las mallas; [visor-3d.css](../../_compartido/css/visor-3d.css) conserva los estilos del diálogo.

Referencias archivadas: [VISOR-modelos-3d.md](referencias/VISOR-modelos-3d.md) (documentación del prototipo), [catalogo-28-formas.png](referencias/catalogo-28-formas.png) (lámina o revisión original).

## Tecnologías y datos

**Tecnologías.** WebGL, Canvas, JavaScript y mallas paramétricas de `UAPMapTools`. El visor es local y no necesita el SDK cartográfico.

**Datos.** No requiere informes para abrir el catálogo. Para vincular cada modelo a un informe se utiliza `standardized_shape`. Véanse los [recursos compartidos](../../_compartido/README.md#datos-necesarios).

## Cómo revisar la referencia

En el [observatorio original](../../../DB%20Test/observatorio.html), abre **Explorar herramientas → Visor de modelos 3D**. Cambia de forma con el selector original.

## Prompt de ejemplo

> Muéstrame el catálogo 3D de formas reportadas y abre el modelo de Triangle para rotarlo.

## Límites y pendientes

Los modelos ilustran etiquetas y algunas categorías tienen símbolos interpretativos. El visor no reproduce el objeto reportado, su tamaño ni una trayectoria. Las formas sin categoría permanecen como puntos en el mapa.
