"""Closed vocabularies Gold derives from Silver's free-text descriptors.

Silver keeps each source's raw text (``sighting.sound``, ``direction``, ``weather``,
``terrain``, ``location.state`` and ``city``). Gold publishes a small closed code per
report so the descriptors can be grouped and filtered. The rules are keyword
matches over the lower-cased text: they never invent a value, and text that does
not match any rule becomes ``other`` (it existed but is not classifiable), while
empty or "unknown" text stays null.
"""
from __future__ import annotations

import re

UNKNOWN = {"", "unk", "unknown", "?", "??", "n/a", "na", "none given", "not stated", "not given", "-", "--"}


def _clean(text) -> str | None:
    if text is None:
        return None
    value = re.sub(r"\s+", " ", str(text)).strip().lower()
    return None if value in UNKNOWN else value


def _first(value: str, rules: list[tuple[str, tuple[str, ...]]]) -> str:
    for code, words in rules:
        if any(re.search(w, value) for w in words):
            return code
    return "other"


# Order matters: the first rule that matches wins ("no sound" is silent, not "sound").
SOUND_RULES = [
    ("silent", (r"^no\b", r"\bno ?sound", r"\bsilen", r"^none$", r"\bquiet\b", r"\bno noise", r"\bnoiseless", r"\bsoundless", r"^nothing")),
    ("humming", (r"hum",)),
    ("buzzing", (r"\bbuzz",)),
    ("whirring", (r"\bwhir", r"\bwhoosh", r"\bswish", r"\brush")),
    ("whistling", (r"\bwhistl", r"\bhiss", r"hi(gh)?.?pitch", r"\bwhin", r"\bscream", r"\bshriek")),
    ("roaring", (r"\broar", r"\brumbl", r"\bthunder", r"\bjet", r"\bengine", r"\bloud")),
    ("explosion", (r"\bbang", r"\bboom", r"\bexplo", r"\bcrack", r"\bpop")),
    ("beeping", (r"\bbeep", r"\bpuls", r"\bclick", r"\btone")),
]
SOUND_LABELS = {"silent": "Silencioso", "humming": "Zumbido grave", "buzzing": "Zumbido", "whirring": "Silbido de aire o giro",
                "whistling": "Pitido o silbido agudo", "roaring": "Rugido o motor", "explosion": "Estallido",
                "beeping": "Pitidos o pulsos", "other": "Otro sonido"}

COMPASS = {"n": "N", "north": "N", "nne": "N", "nnw": "N", "ne": "NE", "northeast": "NE", "north-east": "NE",
           "e": "E", "east": "E", "ene": "E", "ese": "E", "se": "SE", "southeast": "SE", "south-east": "SE",
           "s": "S", "south": "S", "sse": "S", "ssw": "S", "sw": "SW", "southwest": "SW", "south-west": "SW",
           "w": "W", "west": "W", "wsw": "W", "wnw": "W", "nw": "NW", "northwest": "NW", "north-west": "NW"}
DIRECTION_LABELS = {"N": "Norte", "NE": "Noreste", "E": "Este", "SE": "Sureste", "S": "Sur", "SW": "Suroeste",
                    "W": "Oeste", "NW": "Noroeste", "overhead": "En lo alto", "other": "Otra descripción"}

WEATHER_RULES = [
    ("storm", (r"\bstorm", r"\bthunder", r"\blightning")),
    ("snow", (r"\bsnow", r"\bsleet", r"\bhail")),
    ("rain", (r"\brain", r"\bdrizzl", r"\bshower", r"\bwet\b")),
    ("fog", (r"\bfog", r"\bmist", r"\bhaz[ey]", r"\bsmog")),
    ("partly_cloudy", (r"\bpartly", r"\bscattered", r"\bfew cloud", r"\bbroken")),
    ("cloudy", (r"\bcloud", r"\bovercast", r"\bgr[ae]y sky")),
    ("windy", (r"\bwind", r"\bbreez", r"\bgust")),
    ("clear", (r"\bclear", r"\bfair\b", r"\bsunny", r"\bstarry", r"\bcloudless", r"\bfine\b", r"\bcalm\b")),
]
WEATHER_LABELS = {"clear": "Despejado", "partly_cloudy": "Parcialmente nublado", "cloudy": "Nublado", "fog": "Niebla o bruma",
                  "rain": "Lluvia", "snow": "Nieve o granizo", "storm": "Tormenta", "windy": "Viento", "other": "Otra descripción"}

TERRAIN_RULES = [
    ("airborne", (r"\baltitude", r"\bin flight", r"\baircraft", r"\bairborne", r"\bcockpit", r"\bcruis")),
    ("water", (r"\bsea\b", r"\bocean", r"\blake", r"\briver", r"\bbeach", r"\bcoast", r"\bbay\b", r"\bshore", r"\bharbou?r", r"\bport\b")),
    ("mountain", (r"\bmountain", r"\bhill", r"\bvalley", r"\bcanyon", r"\bpeak", r"\bridge\b")),
    ("forest", (r"\bforest", r"\bwood", r"\bjungle", r"\btrees")),
    ("desert", (r"\bdesert", r"\bsand", r"\barid")),
    ("military", (r"\bbase\b", r"\bafb\b", r"\bair force", r"\bmilitary", r"\barmy", r"\bnaval", r"\bmissile", r"\bgate\b")),
    ("road", (r"\broad", r"\bhighway", r"\bfreeway", r"\binterstate", r"\bstreet", r"\bmotorway", r"\bcar\b")),
    ("urban", (r"\bcity", r"\btown", r"\burban", r"\bresidential", r"\bsuburb", r"\bbuilt.?up", r"\bbackyard", r"\bhouse", r"\bhome", r"\bvillage")),
    ("rural", (r"\brural", r"\branch", r"\bfarm", r"\bfield", r"\bcountry", r"\bhomestead", r"\bprairie", r"\bmeadow", r"\bplain")),
]
TERRAIN_LABELS = {"urban": "Urbano o residencial", "rural": "Rural o campo", "forest": "Bosque", "mountain": "Montaña o valle",
                  "water": "Agua o costa", "desert": "Desierto", "military": "Instalación militar", "road": "Carretera",
                  "airborne": "En vuelo", "other": "Otra descripción"}


def sound_type(text) -> str | None:
    value = _clean(text)
    return None if value is None else _first(value, SOUND_RULES)


def direction_code(text) -> str | None:
    value = _clean(text)
    if value is None:
        return None
    if re.search(r"\boverhead|\bzenith|\babove\b", value):
        return "overhead"
    token = re.sub(r"[^a-z\- ]", "", value).strip()
    if token in COMPASS:
        return COMPASS[token]
    # "n to s", "from ne": the first compass word is where the description starts.
    for word in re.findall(r"[a-z\-]+", value):
        if word in COMPASS and (len(word) > 1 or len(value) <= 6):
            return COMPASS[word]
    return "other"


def weather_type(text) -> str | None:
    value = _clean(text)
    return None if value is None else _first(value, WEATHER_RULES)


def terrain_type(text) -> str | None:
    value = _clean(text)
    return None if value is None else _first(value, TERRAIN_RULES)


def vallee_code(text) -> str | None:
    value = _clean(text)
    if value is None:
        return None
    value = value.upper().replace(" ", "")
    return value if re.fullmatch(r"[A-Z]{2,3}\d?", value) else None


VALLEE_FAMILIES = {"FB": "Sobrevuelo", "MA": "Maniobra", "AN": "Anomalía", "CE": "Encuentro cercano", "IFO": "Objeto identificado"}


def vallee_label(code: str) -> str:
    family = VALLEE_FAMILIES.get(code.rstrip("0123456789"))
    return f"{code} — {family}" if family else code


def event_type_code(text) -> str | None:
    value = _clean(text)
    if value is None:
        return None
    value = value.upper().replace(" ", "")
    return value if re.fullmatch(r"[0-9A-Z]{1,4}", value) else None


US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico", "GU": "Guam", "VI": "U.S. Virgin Islands",
}
CA_PROVINCES = {"AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba", "NB": "New Brunswick",
                "NL": "Newfoundland and Labrador", "NS": "Nova Scotia", "NT": "Northwest Territories", "NU": "Nunavut",
                "ON": "Ontario", "PE": "Prince Edward Island", "QC": "Quebec", "SK": "Saskatchewan", "YT": "Yukon"}
AU_STATES = {"NSW": "New South Wales", "VIC": "Victoria", "QLD": "Queensland", "WA": "Western Australia",
             "SA": "South Australia", "TAS": "Tasmania", "ACT": "Australian Capital Territory", "NT": "Northern Territory"}
SUBDIVISIONS = {"US": US_STATES, "CA": CA_PROVINCES, "AU": AU_STATES}
EXTRA_ALIASES = {"US": {"WASH": "WA", "CALIF": "CA", "CALIF.": "CA", "FLA": "FL", "MASS": "MA", "PENN": "PA", "TEX": "TX",
                        "ARIZ": "AZ", "COLO": "CO", "CONN": "CT", "MICH": "MI", "MINN": "MN", "WISC": "WI", "OKLA": "OK",
                        "D.C.": "DC", "WASHINGTON DC": "DC", "WASHINGTON D.C.": "DC"},
                 "CA": {"QUE": "QC", "PQ": "QC", "QB": "QC", "QUEBEC": "QC", "QUÉBEC": "QC", "NF": "NL", "NEWFOUNDLAND": "NL",
                        "LAB": "NL", "LABRADOR": "NL", "PEI": "PE", "NWT": "NT", "NUV": "NU", "YK": "YT"},
                 "AU": {"N.S.W.": "NSW", "QUEENSLAND": "QLD", "TASMANIA": "TAS", "SAU": "SA", "WAU": "WA"}}


def _alias_table() -> dict:
    table = {}
    for country, items in SUBDIVISIONS.items():
        aliases = {}
        for code, name in items.items():
            aliases[code] = code
            aliases[name.upper()] = code
        aliases.update(EXTRA_ALIASES.get(country, {}))
        table[country] = aliases
    return table


ALIASES = _alias_table()


def region_code(state, country_iso2) -> str | None:
    """ISO-like subdivision code ("US-NM") when the state text names one unambiguously.

    Only the United States, Canada and Australia have a closed list here; elsewhere the
    state text of the sources is too heterogeneous to classify without inventing it."""
    if not state or country_iso2 not in ALIASES:
        return None
    value = re.sub(r"\s+", " ", str(state)).strip().upper()
    value = re.sub(r"\s*\(.*\)$", "", value)
    code = ALIASES[country_iso2].get(value) or ALIASES[country_iso2].get(value.rstrip("."))
    return f"{country_iso2}-{code}" if code else None


def region_labels() -> dict:
    countries = {"US": "EE. UU.", "CA": "Canadá", "AU": "Australia"}
    return {f"{c}-{code}": f"{name} ({countries[c]})" for c, items in SUBDIVISIONS.items() for code, name in items.items()}


def city_name(city) -> str | None:
    """Trimmed city text in title case. It is the source's text, not a geocoded place."""
    if city is None:
        return None
    value = re.sub(r"\s+", " ", str(city)).strip(" ,.;")
    if not value or value.lower() in UNKNOWN or len(value) > 80 or not re.search(r"[A-Za-zÀ-ÿ]", value):
        return None
    return value.title()


def witness_band(n) -> str | None:
    if n is None:
        return None
    n = int(n)
    if n <= 0:
        return "w0"
    if n <= 2:
        return f"w{n}"
    if n <= 5:
        return "w3_5"
    if n <= 10:
        return "w6_10"
    return "w11_plus"


WITNESS_LABELS = {"w0": "0 consignados", "w1": "1 testigo", "w2": "2 testigos", "w3_5": "3 a 5", "w6_10": "6 a 10",
                  "w11_plus": "11 o más"}


def pending_pair_band(n: int) -> str:
    if n <= 0:
        return "p0"
    if n <= 2:
        return f"p{n}"
    if n <= 5:
        return "p3_5"
    return "p6_plus"


PENDING_LABELS = {"p0": "Sin coincidencias", "p1": "1 coincidencia", "p2": "2 coincidencias", "p3_5": "3 a 5",
                  "p6_plus": "6 o más"}


def similarity_band(score) -> str | None:
    if score is None:
        return None
    for low, code in ((0.95, "s95"), (0.9, "s90"), (0.8, "s80"), (0.5, "s50")):
        if score >= low:
            return code
    return "s00"


SIMILARITY_LABELS = {"s95": "0,95 o más", "s90": "0,90–0,95", "s80": "0,80–0,90", "s50": "0,50–0,80", "s00": "menos de 0,50"}
