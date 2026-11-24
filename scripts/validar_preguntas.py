#!/usr/bin/env python3
"""Preguntas sobre Silver y Gold y si el Data Agent tiene un gráfico para responderlas.

Cada pregunta del banco lleva su clase:
  G  expresable con el contrato actual: se ejecuta contra la carga Gold aprobada y debe
     devolver filas con su vista. Si alguna falla, el script termina con código 1.
  X  sobre Gold, pero el contrato no la expresa: si hay consulta, es el intento más natural
     y se registra el error del motor; si no, la nota dice qué falta (Pxx = fila de
     docs/auditoria-brechas-gold.md).
  S  solo Silver tiene el dato: Gold no lo publica.
  N  el dato no existe en Silver ni en Gold (o no existe por diseño): ninguna vista puede responderla.

Uso (desde la raíz):
  apps/api/.venv/bin/python scripts/validar_preguntas.py [--json salida.json]

Resultado documentado en docs/preguntas-y-graficos.md.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))
R, M, E, ER = "fact_report", "report_model_output", "fact_event", "event_report"
US = {"column": "country_iso2", "op": "eq", "value": "US"}
UFOCAT = {"column": "source_code", "op": "eq", "value": "UFOCAT"}
def yr(a, b): return [{"column": "event_year", "op": "gte", "value": a}, {"column": "event_year", "op": "lte", "value": b}]
def q(dataset, view="bars", group_by=(), metrics=("report_count",), filters=(), elig=(), **kw):
    out = {"dataset": dataset, "view": view, "group_by": list(group_by), "metrics": list(metrics),
           "filters": list(filters), "eligibility": list(elig)}
    out.update(kw)
    return out

BANK = [
 # ---------------- Volumen, fuentes y procedencia
 ("Volumen y procedencia", "¿Cuántos informes hay en total?", "G", q("agg_source", "table", metrics=["report_count"])),
 ("Volumen y procedencia", "¿Cuántos informes aporta cada fuente?", "G", q("agg_source", group_by=["source_code"], order_by="report_count")),
 ("Volumen y procedencia", "¿De qué orígenes (NUFORC, MUFON, Blue Book…) vienen los informes?", "G", q("agg_source", group_by=["origin_code"], order_by="report_count")),
 ("Volumen y procedencia", "¿Cuántos informes vienen de NUFORC?", "G", q("agg_source", "table", filters=[{"column": "origin_code", "op": "eq", "value": "NUFORC"}])),
 ("Volumen y procedencia", "¿Qué colección contiene cada fuente?", "G", q("agg_source", "matrix", group_by=["collection_code", "source_code"])),
 ("Volumen y procedencia", "¿Qué orígenes aparecen dentro de cada fuente?", "G", q("agg_source", "matrix", group_by=["source_code", "origin_code"])),
 ("Volumen y procedencia", "¿Qué fuente tiene más informes con evidencia externa?", "G", q("agg_source", group_by=["source_code"], metrics=["external_evidence_reports", "external_evidence_pct"])),
 ("Volumen y procedencia", "¿Desde qué año y hasta qué año tiene informes cada fuente?", "G", q("agg_year", "table", group_by=["source_code"], metrics=["first_year", "last_year"])),
 ("Volumen y procedencia", "¿Cómo cambia la mezcla de fuentes por década?", "G", q("agg_year", "stacked", group_by=["decade", "source_code"], order_by="decade", descending=False, limit=500)),
 ("Volumen y procedencia", "¿Cuánto aportó cada fuente al cambio entre 2000–2009 y 2010–2019? (cascada)", "G", {"analysis": "period_change", "params": {'period': 'decade', 'from': 2000, 'to': 2010}}),
 ("Volumen y procedencia", "¿En qué fuente se concentra cada origen (fuente dominante y su porcentaje)?", "G", {"analysis": "dominant_share", "params": {}}),
 ("Volumen y procedencia", "¿Cuántos informes de cada fuente reutilizan un ID de su archivo de origen?", "G", q(R, group_by=["source_code"], metrics=["reused_id_reports", "reused_id_pct"])),

 # ---------------- Tiempo
 ("Tiempo", "¿Cómo evolucionan los informes por año?", "G", q("agg_year", "timeseries", group_by=["event_year"], filters=yr(1900, 2025), order_by="event_year", descending=False, limit=500)),
 ("Tiempo", "¿Cuántos informes hay por década?", "G", q("agg_year", "timeseries", group_by=["decade"], filters=yr(1900, 2025), order_by="decade", descending=False)),
 ("Tiempo", "¿Qué año tuvo más informes?", "G", q("agg_year", "timeseries", group_by=["event_year"], filters=yr(1900, 2025), order_by="event_year", descending=False, limit=500)),
 ("Tiempo", "¿Cómo evoluciona cada fuente año a año?", "G", q("agg_year", "timeseries", group_by=["event_year", "source_code"], filters=yr(1940, 2022), order_by="event_year", descending=False, limit=500)),
 ("Tiempo", "¿Qué meses del año acumulan más informes?", "G", q("agg_month", group_by=["event_month"], order_by="event_month", descending=False)),
 ("Tiempo", "¿Hay picos o estacionalidad mes a mes entre 1990 y 2020?", "G", q("agg_month", "month_calendar", group_by=["event_year", "event_month"], filters=yr(1990, 2020), limit=12 * 31)),
 ("Tiempo", "¿Cómo evoluciona la serie mensual (año-mes) desde 2000?", "G", q("agg_month", "timeseries", group_by=["year_month"], filters=yr(2000, 2022), order_by="year_month", descending=False, limit=500)),
 ("Tiempo", "¿Qué días de la semana y a qué hora se consignan más informes?", "G", q("agg_weekday_hour", "hour_weekday", group_by=["weekday", "event_hour"], limit=200)),
 ("Tiempo", "¿A qué hora del día se reportan más?", "G", q(R, group_by=["event_hour"], elig=["hour"], order_by="event_hour", descending=False)),
 ("Tiempo", "¿Qué día de la semana tiene más informes?", "G", q(R, group_by=["weekday"], elig=["day"], order_by="weekday", descending=False)),
 ("Tiempo", "¿Qué pasó el 13 de marzo de 1997 (luces de Phoenix)?", "G",
  {"dataset": R, "view": "timeline", "filters": [{"column": "event_date", "op": "eq", "value": "1997-03-13"}], "eligibility": ["day"], "limit": 200}),
 ("Tiempo", "¿Qué fechas concretas acumulan más informes?", "G", q(R, group_by=["event_date"], elig=["day"], order_by="report_count", limit=20)),
 ("Tiempo", "¿Cómo se reparte la hora consignada dentro de cada mes (mes × hora)?", "G", q(R, "matrix", group_by=["event_month", "event_hour"], elig=["month", "hour"], limit=300)),
 ("Tiempo", "¿Qué fechas quedan muy por encima de su referencia local de 28 días? (picos anómalos)", "G", {"analysis": "daily_anomalies", "params": {'from_year': 1990, 'to_year': 2022}}),
 ("Tiempo", "¿Cuánto cambió cada mes respecto al mismo mes del año anterior?", "G", {"analysis": "yoy_change", "params": {'from_year': 1991, 'to_year': 2022}}),
 ("Tiempo", "¿Qué mes tiene el volumen diario típico más alto? (cajas por día)", "G", {"analysis": "daily_distribution_by_month", "params": {'from_year': 1990, 'to_year': 2022}}),
 ("Tiempo", "¿En qué meses la hora consignada se aleja más del patrón global?", "G", {"analysis": "hour_month_deviation", "params": {}}),

 # ---------------- Geografía
 ("Geografía", "¿Qué países tienen más informes?", "G", q("agg_country", group_by=["country_iso2"], order_by="report_count", limit=15)),
 ("Geografía", "Mapa de informes por país", "G", q("agg_country", "choropleth", group_by=["country_iso2"], limit=300)),
 ("Geografía", "¿Cuántos informes hay en México?", "G", q("agg_country", "table", filters=[{"column": "country_iso2", "op": "eq", "value": "MX"}])),
 ("Geografía", "¿En cuántos países distintos hay informes?", "G", q("agg_country", "table", metrics=["distinct_country_count"])),
 ("Geografía", "¿Dónde se concentran los informes (celdas de 5°)?", "G", q("agg_spatial_cell", "density", group_by=["cell_lat", "cell_lng"], filters=[{"column": "resolution_deg", "op": "eq", "value": 5}], limit=20000)),
 ("Geografía", "¿Dónde se concentran en celdas de 1° en Estados Unidos?", "G", q(R, "density", group_by=["cell1_lat", "cell1_lng"], filters=[US], elig=["map", "country"], limit=20000)),
 ("Geografía", "Muéstrame los informes de Brasil en el mapa", "G", {"dataset": R, "view": "points", "filters": [{"column": "country_iso2", "op": "eq", "value": "BR"}], "eligibility": ["map", "country"], "limit": 500}),
 ("Geografía", "Muéstrame en un globo todos los informes con coordenadas", "G", {"dataset": R, "view": "globe", "metrics": ["report_count"], "eligibility": ["map"]}),
 ("Geografía", "¿Cuántos informes hay en el área que dibujé (Rectángulo/Lazo)?", "G",
  {"dataset": R, "view": "points", "eligibility": ["map"], "limit": 500, "area": [[-112.5, 33.0], [-111.5, 33.0], [-111.5, 34.0], [-112.5, 34.0]]}),
 ("Geografía", "¿Cómo cambió el top de países por década?", "G", q("fact_report", "matrix", group_by=["country_iso2", "decade"], elig=["country", "calendar"], filters=[{"column": "country_iso2", "op": "in", "value": ["US", "CA", "GB", "AU", "BR", "MX", "FR", "DE"]}], limit=500)),
 ("Geografía", "¿Qué formas predominan en cada país?", "G", q(R, "matrix", group_by=["country_iso2", "shape_code"], elig=["country"], filters=[{"column": "country_iso2", "op": "in", "value": ["US", "CA", "GB", "AU"]}], limit=200)),
 ("Geografía", "¿De qué fuente vienen los informes de cada país?", "G", q("agg_country", "stacked", group_by=["country_iso2", "source_code"], filters=[{"column": "country_iso2", "op": "in", "value": ["US", "CA", "GB", "AU", "BR", "MX"]}], limit=100)),
 ("Geografía", "¿Cuántos informes hay en California / Texas / una ciudad?", "G", q(R, "table", filters=[{"column": "region_code", "op": "in", "value": ["US-CA", "US-TX"]}], elig=["country"], group_by=["region_code"])),
 ("Geografía", "¿Cuántos informes por 100.000 habitantes tiene cada país?", "N", None, "Ni Silver ni Gold tienen población; habría que incorporar una fuente externa fijada."),
 ("Geografía", "¿Cuándo aparece por primera vez cada celda de 1° (crecimiento de cobertura)?", "G", {"analysis": "first_appearance", "params": {'resolution': 1, 'from_year': 1940}}),
 ("Geografía", "¿Qué países entraron o salieron del top 10 acumulado desde 1940? (bump chart)", "G", {"analysis": "rank_over_time", "params": {'from_year': 1940, 'to_year': 2022}}),
 ("Geografía", "¿Qué proporción de informes cae en el 1 % de celdas más concurridas?", "G", {"analysis": "concentration", "params": {'resolution': 1}}),
 ("Geografía", "¿Qué celdas de EE. UU. subieron o bajaron entre 2000s y 2010s?", "G", {"analysis": "cell_change", "params": {"from": 2000, "to": 2010, "filters": [US]}}),
 ("Geografía", "¿Cuántas fuentes distintas contribuyen a cada celda?", "G", q(R, "density", group_by=["cell1_lat", "cell1_lng"], metrics=["distinct_source_count"], elig=["map"], limit=20000)),
 ("Geografía", "¿Qué celdas acumulan ≥4 informes en una misma semana? (clusters)", "G", {"analysis": "clusters", "params": {'method': 'week_cell'}}),

 # ---------------- Descriptores del relato
 ("Descriptores", "¿Qué formas se reportan más?", "G", q("agg_shape", group_by=["shape_code"], order_by="report_count", limit=28)),
 ("Descriptores", "¿Cuántos informes de triángulos hay?", "G", q("agg_shape", "table", filters=[{"column": "shape_code", "op": "eq", "value": "Triangle"}])),
 ("Descriptores", "¿Qué formas ganaron o perdieron peso entre los 70 y los 2000?", "G", q(R, "dumbbell", group_by=["decade", "shape_code"], filters=[{"column": "decade", "op": "in", "value": [1970, 2000]}], elig=["calendar"], limit=100)),
 ("Descriptores", "¿Cómo cambia la mezcla de formas por década?", "G", q(R, "stacked", group_by=["decade", "shape_code"], elig=["calendar"], filters=[{"column": "shape_code", "op": "ne", "value": "Unknown"}, {"column": "decade", "op": "gte", "value": 1900}], limit=500)),
 ("Descriptores", "¿Qué fuentes aportan cada forma?", "G", q("agg_shape", "matrix", group_by=["shape_code", "source_code"], limit=200)),
 ("Descriptores", "¿De qué colores se reportan?", "G", q(R, group_by=["color_family"], order_by="report_count")),
 ("Descriptores", "¿Cuántos informes de color rojo exacto (tono)?", "G", q(R, group_by=["color_code"], order_by="report_count", limit=21)),
 ("Descriptores", "¿Qué colores tienen las esferas?", "G", q(R, group_by=["color_family"], filters=[{"column": "shape_code", "op": "eq", "value": "Sphere"}], order_by="report_count")),
 ("Descriptores", "¿Qué forma y color aparecen juntos?", "G", q(R, "matrix", group_by=["shape_code", "color_family"], limit=500)),
 ("Descriptores", "¿Cómo se mueven los objetos reportados?", "G", q(R, group_by=["movement_type"], order_by="report_count")),
 ("Descriptores", "¿Qué movimiento tiene cada forma?", "G", q(R, "matrix", group_by=["shape_code", "movement_type"], limit=200)),
 ("Descriptores", "¿Cuánto duran en general (tramos)?", "G", q(R, group_by=["duration_bucket"])),
 ("Descriptores", "¿Cómo se distribuye la duración en minutos?", "G", {"dataset": R, "view": "histogram", "metrics": ["report_count"]}),
 ("Descriptores", "¿Qué porcentaje dura hasta 5 minutos?", "G", {"dataset": R, "view": "ecdf", "metrics": ["report_count"]}),
 ("Descriptores", "¿Cuánto duran los triángulos frente a los discos?", "G", q(R, "matrix", group_by=["shape_code", "duration_bucket"], filters=[{"column": "shape_code", "op": "in", "value": ["Triangle", "Disc"]}])),
 ("Descriptores", "¿Qué clases Hynek (CE1, CE2, CE3…) aparecen?", "G", q(R, group_by=["hynek"], order_by="report_count", limit=40)),
 ("Descriptores", "¿Cuántos informes mencionan medios (foto/video)?", "G", q(R, group_by=["source_code"], metrics=["media_reports", "media_pct"])),
 ("Descriptores", "¿Qué fuentes tienen más informes con descripción?", "G", q(R, group_by=["source_code", "has_description"])),
 ("Descriptores", "¿Cuántos testigos suele tener un informe?", "G", q(R, group_by=["witness_band"])),
 ("Descriptores", "¿Duran más los informes con más testigos? (dispersión)", "G", {"dataset": R, "view": "scatter", "metrics": ["report_count"], "measure": "duration_witnesses"}),
 ("Descriptores", "¿Cuál es la mediana de duración por forma?", "G", q(R, "boxplot", group_by=["shape_code"], metrics=["median_duration_min"])),
 ("Descriptores", "¿Dónde están las duraciones largas de la cola (> 1 h)?", "G", {"dataset": R, "view": "histogram", "metrics": ["report_count"], "measure": "duration_tail"}),
 ("Descriptores", "¿Qué sonido, dirección o clima describen los testigos?", "G", q(R, group_by=["sound_type"], order_by="report_count")),
 ("Descriptores", "¿Qué clasificación Vallée o tipo de evento tienen?", "G", q(R, group_by=["vallee_code"], order_by="report_count", limit=40)),
 ("Descriptores", "¿Qué etiquetas de comportamiento aparecen (flota, cambia de color…)?", "G", q("report_behavior_tag", group_by=["behavior_tag"], order_by="report_count")),
 ("Descriptores", "¿Qué dice el texto original del testigo?", "N", None, "Bronze y Silver no conservan el relato: solo el indicador has_description y las puntuaciones derivadas."),
 ("Descriptores", "¿Cuántos objetos se vieron en cada informe?", "N", None, "Solo Bronze tiene num_objects; Silver no lo conserva, así que Gold no puede publicarlo sin cambiar Silver."),

 # ---------------- Proximidad a instalaciones
 ("Proximidad", "¿Cuántos informes hay a menos de 10, 25, 50… km de una instalación?", "G", q("agg_nuclear_band", group_by=["distance_band"], order_by="distance_band", descending=False)),
 ("Proximidad", "¿Qué instalaciones quedan como las más cercanas a más informes?", "G", q("agg_nuclear_band", group_by=["nearest_facility_key"], order_by="report_count", limit=15)),
 ("Proximidad", "¿Cuántos informes hay cerca de Hanford?", "G", q("agg_nuclear_band", group_by=["distance_band"], filters=[{"column": "nearest_facility_key", "op": "eq", "value": "hanford-site"}])),
 ("Proximidad", "¿Qué distancia media a la instalación más cercana tiene cada país?", "G", q(R, group_by=["country_iso2"], metrics=["avg_nuclear_distance_km"], elig=["country", "nuclear_proximity"], filters=[{"column": "country_iso2", "op": "in", "value": ["US", "CA", "GB", "AU"]}])),
 ("Proximidad", "¿Cambia la distancia por década?", "G", q(R, "stacked", group_by=["decade", "distance_band"], elig=["calendar", "nuclear_proximity"], filters=[{"column": "decade", "op": "gte", "value": 1900}], limit=500)),
 ("Proximidad", "¿Qué porcentaje de cada país está a menos de 10 km? (coropleta de %)", "G", q(R, "choropleth", group_by=["country_iso2"], metrics=["within_10km_pct"], elig=["country"], limit=300)),
 ("Proximidad", "¿Cómo se distribuye la distancia exacta (curva acumulada en km)?", "G", {"dataset": R, "view": "ecdf", "metrics": ["report_count"], "measure": "nuclear_distance", "group_by": ["source_code"], "eligibility": ["nuclear_proximity"]}),
 ("Proximidad", "¿Qué celdas conectan con qué instalación? (mapa de enlaces)", "G", {"analysis": "facility_links", "params": {}}),
 ("Proximidad", "¿Qué encuentros nucleares (misiles afectados, sistema de armas) hay?", "G", {"dataset": "fact_nuclear_encounter", "view": "points", "eligibility": ["map"]}),
 ("Proximidad", "¿Qué instalaciones del catálogo excluido existen?", "G", q("facility_catalog", group_by=["facility_type", "admitted"], metrics=["facility_count"])),

 # ---------------- Duplicados y eventos
 ("Duplicados y eventos", "¿Cuántos eventos confirmados hay?", "G", q(E, "table", metrics=["event_count", "event_member_reports"])),
 ("Duplicados y eventos", "¿Qué tamaño tienen los grupos confirmados?", "G", q(E, group_by=["member_count"], metrics=["event_member_reports"], order_by="member_count", descending=False)),
 ("Duplicados y eventos", "¿Cuántos informes hay por estado de duplicado?", "G", q(R, group_by=["duplicate_status"])),
 ("Duplicados y eventos", "¿Qué fuentes tienen más coincidencias por revisar?", "G", q("agg_source", group_by=["source_code"], metrics=["pending_candidate_reports", "pending_candidate_pct"])),
 ("Duplicados y eventos", "¿Cómo evolucionan por año los eventos confirmados?", "G", q(E, "timeseries", group_by=["event_year"], metrics=["event_count"], elig=["calendar"], order_by="event_year", descending=False, limit=500)),
 ("Duplicados y eventos", "¿Cuántos ovnis reales / eventos únicos hubo?", "N", None, "No existe por diseño: el archivo cuenta informes y eventos confirmados; el agente lo explica sin gráfico."),
 ("Duplicados y eventos", "¿Cuántas coincidencias por revisar tiene cada informe marcado?", "G", q(R, group_by=["pending_pair_band"])),
 ("Duplicados y eventos", "¿Qué similitud y método tiene cada par candidato?", "G", q("candidate_pair", group_by=["match_method"], metrics=["pair_count", "avg_similarity"])),

 # ---------------- Calidad, cobertura y elegibilidad
 ("Calidad y cobertura", "¿Cuántos informes quedan fuera de cada análisis (mapa, país, hora…)?", "G", q("agg_coverage", "stacked", group_by=["aggregate_code", "coverage_status"])),
 ("Calidad y cobertura", "¿Por qué motivos quedan fuera del mapa?", "G", q(R, group_by=["map_exclusion"], order_by="report_count")),
 ("Calidad y cobertura", "¿Qué precisión de fecha tiene cada fuente?", "G", q(R, "stacked", group_by=["source_code", "calendar_precision"])),
 ("Calidad y cobertura", "¿Cuál es el estado y la certeza de las fechas?", "G", q(R, "matrix", group_by=["date_status", "date_certainty"])),
 ("Calidad y cobertura", "¿Qué precisión de reloj tiene cada fuente?", "G", q(R, "stacked", group_by=["source_code", "clock_precision"])),
 ("Calidad y cobertura", "¿Qué fuentes tienen marcadores de día?", "G", q(R, "stacked", group_by=["source_code", "day_placeholder_risk"])),
 ("Calidad y cobertura", "¿De dónde vienen las coordenadas (Bronze o catálogo externo)?", "G", q(R, "stacked", group_by=["source_code", "coordinate_basis"])),
 ("Calidad y cobertura", "¿Qué estado tienen los países (válido, contradictorio…)?", "G", q(R, group_by=["country_status"])),
 ("Calidad y cobertura", "¿Qué porcentaje de cada fuente tiene país, día y coordenadas a la vez?", "G", q(R, group_by=["source_code"], metrics=["core_fields_pct"])),
 ("Calidad y cobertura", "¿Qué combinaciones de datos faltantes se repiten? (UpSet)", "G", {"analysis": "missing_combinations", "params": {}}),
 ("Calidad y cobertura", "¿Cómo cambió el % con coordenadas utilizables por año?", "G", q(R, "timeseries", group_by=["event_year", "source_code"], metrics=["map_usable_pct"], elig=["calendar"], filters=yr(1940, 2022), order_by="event_year", descending=False, limit=500)),
 ("Calidad y cobertura", "¿Dónde se pierde cobertura de año a mes, día y hora? (embudo)", "G", {"analysis": "funnel", "params": {}}),
 ("Calidad y cobertura", "¿Qué reglas de calidad dispararon más incidencias?", "G", q("quality_issue_summary", group_by=["rule_id"], metrics=["issue_count"], order_by="issue_count", limit=30)),
 ("Calidad y cobertura", "¿Qué cambió Silver respecto a Bronze en cada informe?", "G", q("silver_change_summary", group_by=["rule_id"], metrics=["change_count"], order_by="change_count", limit=30)),
 ("Calidad y cobertura", "¿Qué texto original de fecha u hora tenía el informe?", "G", {"analysis": "compare_reports", "params": {"report_ids": [8137, 8138]}}),

 # ---------------- Salidas de modelo
 ("Salidas de modelo", "¿Qué probabilidad media de engaño asigna el modelo por fuente?", "G", q(M, group_by=["source_code"], metrics=["avg_hoax_likelihood", "scored_reports"])),
 ("Salidas de modelo", "¿Qué calidad documental media tiene cada forma?", "G", q(M, group_by=["shape_code"], metrics=["avg_quality_score"], order_by="avg_quality_score", limit=28)),
 ("Salidas de modelo", "¿Cómo evoluciona el sentimiento VADER por año?", "G", q(M, "timeseries", group_by=["event_year"], metrics=["avg_vader_compound"], filters=yr(1940, 2022), elig=["calendar"], order_by="event_year", descending=False, limit=500)),
 ("Salidas de modelo", "¿Qué sentimiento RoBERTa tiene cada país?", "G", q(M, "choropleth", group_by=["country_iso2"], metrics=["avg_roberta_sentiment"], elig=["country"], limit=300)),
 ("Salidas de modelo", "¿Qué emoción dominante predomina (7 clases)?", "G", q(M, group_by=["emotion_7_dominant"], order_by="report_count")),
 ("Salidas de modelo", "¿Qué tono (positivo/negativo) tienen los relatos?", "G", q(M, group_by=["emotion_28_group"])),
 ("Salidas de modelo", "¿Qué emoción domina en cada fuente?", "G", q(M, "stacked", group_by=["source_code", "emotion_7_dominant"])),
 ("Salidas de modelo", "¿Qué emoción fina (28 clases) domina?", "G", q(M, group_by=["emotion_28_dominant"], order_by="report_count", limit=30)),
 ("Salidas de modelo", "¿Qué riqueza media tiene cada fuente?", "G", q(M, group_by=["source_code"], metrics=["avg_richness_score", "median_richness_score"])),
 ("Salidas de modelo", "¿Cómo se reparte la puntuación de sentimiento? (histograma)", "G", {"dataset": M, "view": "histogram", "metrics": ["report_count"], "measure": "sentiment", "group_by": ["source_code"]}),
 ("Salidas de modelo", "¿Cuánto difieren VADER y RoBERTa? (dispersión)", "G", {"dataset": M, "view": "scatter", "metrics": ["report_count"], "measure": "vader_roberta"}),
 ("Salidas de modelo", "¿Qué puntuaciones NRC (miedo, alegría…) tiene el relato?", "G", q(M, group_by=["source_code"], metrics=["avg_nrc_fear", "avg_nrc_joy", "avg_nrc_surprise", "avg_nrc_trust"])),
 ("Salidas de modelo", "¿Qué banderas de engaño activó el modelo?", "G", q("report_hoax_flag", group_by=["hoax_flag"])),
 ("Salidas de modelo", "¿Qué perfiles de duración y testigos aparecen con K-means?", "G", {"analysis": "kmeans_profiles", "params": {'k': 4}}),

 # ---------------- Registros especiales y comparación de casos
 ("Casos y registros especiales", "¿En qué se parecen los informes #8137 y #8138?", "G", {"analysis": "compare_reports", "params": {"report_ids": [8137, 8138]}}),
 ("Casos y registros especiales", "¿Qué casos de recuperación de naves (crash retrieval) hay?", "G", {"dataset": "fact_crash_retrieval", "view": "points", "eligibility": ["map"]}),
 ("Casos y registros especiales", "¿Qué informes hay en Roswell (Nuevo México) en julio de 1947?", "G",
  {"dataset": R, "view": "timeline", "filters": [{"column": "region_code", "op": "eq", "value": "US-NM"}, {"column": "city_name", "op": "eq", "value": "Roswell"},
   {"column": "event_year", "op": "eq", "value": 1947}, {"column": "event_month", "op": "eq", "value": 7}], "eligibility": ["day", "country"], "limit": 500}),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", type=Path, help="escribe el resultado completo en este archivo")
    args = parser.parse_args()
    from app.gold import QueryError, get_analytics, gold_analysis

    analytics = get_analytics()
    results, failed = [], 0
    for n, entry in enumerate(BANK, 1):
        family, question, kind, query = entry[:4]
        rec = {"n": n, "family": family, "question": question, "kind": kind,
               "note": entry[4] if len(entry) > 4 else "", "query": query}
        if query is not None:
            try:
                r = gold_analysis.analyze(analytics, query) if "analysis" in query else analytics.query(query)
                rec.update(status="ok", view=r["view"], rows=r["row_count"], truncated=r["truncated"],
                           matched=r["matched_source_rows"])
            except QueryError as exc:
                rec.update(status="error", code=exc.code, error=str(exc))
        if kind == "G" and (rec.get("status") != "ok" or not rec.get("rows")):
            failed += 1
        results.append(rec)
        shown = rec.get("view") or rec.get("code") or "-"
        rows = f" {rec['rows']}{'+' if rec.get('truncated') else ''} filas" if rec.get("status") == "ok" else ""
        print(f"{n:3} {kind} {shown:15}{rows:14} {question}")
    totals = {k: sum(r["kind"] == k for r in results) for k in "GXSN"}
    print(f"\n{len(results)} preguntas: {totals['G']} con gráfico, {totals['X']} sin gráfico en Gold, "
          f"{totals['S']} solo en Silver, {totals['N']} sin el dato. Fallos en G: {failed}.")
    if args.json:
        args.json.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
