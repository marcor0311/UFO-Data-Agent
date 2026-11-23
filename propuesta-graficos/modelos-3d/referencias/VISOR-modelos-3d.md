# Catálogo 3D por categoría normalizada

Acceso: **Explorar herramientas → Visor de modelos 3D**.

Mapa y visor usan exclusivamente el catálogo compartido `UAPMapTools.MODEL_FORMS`: 28 valores de `standardized_shape`, con los nombres originales en inglés y una geometría distinta por categoría. El visor ya no mezcla modelos anteriores con actuales.

Changing, Formation, Cloud, Light, Fireball, Flash, Star, Other y Unknown tienen representaciones simbólicas, no reconstrucciones físicas. Other y Unknown permanecen diferenciadas. NULL/Sin clasificar no recibe un modelo; conserva su punto y ficha. La forma original permanece en los datos de la ficha, sin usarse como fallback analítico.

Los modelos tienen tres niveles de geometría, caché y presupuestos de instancias/triángulos. La simplificación conserva la categoría. Modelo que no cabe en el presupuesto o encuadre conserva su punto y sus registros. El visor utiliza un solo contexto WebGL y libera recursos al cerrar; rotación mediante arrastre/flechas, selector individual, acercamiento y restablecimiento. Los distintos motores de iluminación pueden cambiar la apariencia del material, pero ambos consumen las mismas mallas y colores.

Auditoría: 84 combinaciones categoría/LOD pasan el normalizador real deck.gl/luma del build protegido; pruebas de 28 geometrías distintas y presupuestos, 28 capas del adaptador del mapa, y 28 selecciones del visor con GPU simulada. Se inspeccionó `verificacion-experiencia/catalogo-28-formas.png` con view_image; es un render de componentes independiente, no una captura de la aplicación. Revisión real de aplicación/GPU/FPS pendiente por la restricción del navegador.
