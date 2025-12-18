"""
analyze_bio.py

Analizador heurístico de biografías (bio) y captions para inferir posible dedicación/ocupación.
Lee un archivo JSON con la estructura generada por tu scraper (followers_data_{profile}.json)
y produce un archivo JSON/CSV/XLSX con la clasificación por usuario.

Uso:
    python analyze_bio.py
Se te pedirá la ruta al archivo JSON (puedes arrastrarla o pegarla).
Si dejas vacío, el script intenta detectar el último followers_data_*.json en ./results/.

Salida:
    results/analysis_bio_{profile}.json
    results/analysis_bio_{profile}.csv
    results/analysis_bio_{profile}.xlsx

Nota:
- Método heurístico basado en palabras clave. No usa modelos ML externos.
- Configura o amplía KEYWORD_MAP para mejorar la detección.
"""

import json
import re
import sys
from pathlib import Path
from collections import defaultdict, Counter

import pandas as pd

# ------------------------
# Configuración de keywords
# ------------------------
# Mapeo: etiqueta -> lista de palabras clave (en minúscula). Amplía según lo necesites.
KEYWORD_MAP = {
    "developer": ["developer", "desarrollador", "engineer", "ingeniero", "software", "backend", "frontend", "fullstack", "programmer", "python", "java", "javascript", "react", "nodejs"],
    "student": ["student", "estudiante", "universidad", "facultad", "grado", "alumno"],
    "photographer": ["photographer", "fotógraf", "fotografo", "fotografía", "photo", "foto", "fotograf"],
    "influencer": ["influencer", "content creator", "creador de contenido", "colabs", "sponsored", "brand", "ambassador"],
    "model": ["model", "modelo", "agency", "agencia"],
    "musician": ["musician", "cantante", "música", "músico", "dj", "singer", "guitar", "banda"],
    "dancer": ["bailarin", "bailarina", "dancer", "danza", "dance"],
    "chef": ["chef", "cocinero", "cocinera", "cocina", "foodie", "chefpatissier"],
    "fitness": ["trainer", "entrenador", "fitness", "gym", "crossfit", "personal trainer", "fit", "salud"],
    "journalist": ["journalist", "periodista", "reporter", "reportera", "editor"],
    "teacher": ["teacher", "profesor", "docente", "educador"],
    "business": ["ceo", "founder", "co-founder", "emprendedor", "empresa", "startup", "entrepreneur", "negocios"],
    "designer": ["diseñador", "designer", "ux", "ui", "graphic", "diseño", "illustrator"],
    "writer": ["writer", "autor", "escritor", "blogger", "blog"],
    "gamer": ["gamer", "streamer", "twitch", "gaming"],
    "travel": ["travel", "viajes", "viajero", "traveler", "travel blogger"],
    # agrega más etiquetas y palabras claves según tu dominio
}

# Ponderaciones (qué tanto aporta la bio y qué tanto las captions)
WEIGHT_BIO = 0.75
WEIGHT_CAPTIONS = 0.25

# Umbral mínimo de score para asignar una categoría
SCORE_THRESHOLD = 0.08  # ajustable (0.0 - 1.0) - valores pequeños porque normalizamos por keyword counts

# ------------------------
# Utilidades
# ------------------------
RE_EMOJI = re.compile(
    "[" 
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags (iOS)
    "]+", flags=re.UNICODE)


def clean_text(text: str) -> str:
    """Limpia texto: lower, elimina emojis y caracteres raros, normaliza espacios."""
    if text is None:
        return ""
    text = str(text)
    text = RE_EMOJI.sub(" ", text)
    text = text.replace("•", " ").replace("·", " ")
    # eliminar URLs
    text = re.sub(r"https?://\S+", " ", text)
    # eliminar non-alphanumeric excepto # @ . _
    text = re.sub(r"[^0-9a-zA-ZáéíóúüñÁÉÍÓÚÜÑ#@_\s\.\,]", " ", text)
    text = text.lower().strip()
    # normalizar espacios
    text = re.sub(r"\s+", " ", text)
    return text


def tokenize(text: str):
    """Tokenizador simple por palabras y hashtags, retorna lista de tokens únicos."""
    text = clean_text(text)
    tokens = re.findall(r"[#@]?\w+", text)
    return tokens


def score_text_against_keywords(text_tokens, keyword_map):
    """
    Devuelve un dict {label: match_count} indicando cuántas keywords
    del mapping aparecen en los tokens (incluye stems parciales).
    """
    counts = defaultdict(int)
    tokens_set = set(text_tokens)
    joined = " ".join(text_tokens)

    for label, keywords in keyword_map.items():
        # contar coincidencias exactas y por presencia substring
        matches = 0
        for kw in keywords:
            kw = kw.lower()
            # palabra exacta
            if kw in tokens_set:
                matches += 1
            else:
                # substring en el texto completo para capturar "fotografo" vs "fotografía"
                if re.search(r"\b" + re.escape(kw) + r"\b", joined):
                    matches += 1
                else:
                    # también permitir substring más flexible
                    if kw in joined:
                        matches += 1
        counts[label] = matches
    return counts


def normalize_scores(raw_counts, keyword_map):
    """
    Normaliza counts por el número de keywords definidas (para cada label),
    produciendo un valor entre 0 y 1.
    """
    normalized = {}
    for label, count in raw_counts.items():
        total_keywords = max(1, len(keyword_map.get(label, [])))
        normalized[label] = count / total_keywords
    return normalized


# ------------------------
# Lógica principal
# ------------------------
def classify_profile(bio: str, captions: list, keyword_map=KEYWORD_MAP):
    """
    Clasifica un perfil usando bio y captions. Devuelve:
      - best_label (o "unknown")
      - score (float)
      - details dict con scores y matches
    """
    bio_tokens = tokenize(bio)
    cap_tokens = []
    if captions:
        for c in captions:
            cap_tokens += tokenize(c)

    # contar coincidencias
    bio_counts = score_text_against_keywords(bio_tokens, keyword_map)
    cap_counts = score_text_against_keywords(cap_tokens, keyword_map)

    # normalizar por keywords por label
    bio_norm = normalize_scores(bio_counts, keyword_map)
    cap_norm = normalize_scores(cap_counts, keyword_map)

    # combinar con ponderaciones
    combined = {}
    for label in keyword_map.keys():
        combined_score = WEIGHT_BIO * bio_norm.get(label, 0.0) + WEIGHT_CAPTIONS * cap_norm.get(label, 0.0)
        combined[label] = combined_score

    # obtener matches (qué keywords aparecieron) - simple: list tokens that contain keyword substrings
    matches = {}
    text_joined = clean_text(bio + " " + (" ".join(captions) if captions else ""))
    for label, kwlist in keyword_map.items():
        found = [kw for kw in kwlist if kw in text_joined]
        matches[label] = found

    # ordenar labels por score
    sorted_labels = sorted(combined.items(), key=lambda x: x[1], reverse=True)
    best_label, best_score = sorted_labels[0]

    if best_score < SCORE_THRESHOLD:
        best_label = "unknown"

    details = {
        "scores": combined,
        "bio_counts": bio_counts,
        "cap_counts": cap_counts,
        "matches": matches
    }

    return best_label, float(best_score), details


# ------------------------
# I/O y main
# ------------------------
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_outputs(profile_name, records, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"analysis_bio_{profile_name}.json"
    csv_path = out_dir / f"analysis_bio_{profile_name}.csv"
    xlsx_path = out_dir / f"analysis_bio_{profile_name}.xlsx"

    # Guardar JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    # Guardar CSV y XLSX (convertir a DataFrame)
    df = pd.DataFrame(records)
    # Expandir scores (opcional) - convertir dict a columna json-string para lectura
    df["scores_json"] = df["detail"].apply(lambda d: json.dumps(d.get("scores", {}), ensure_ascii=False))
    df["matches_json"] = df["detail"].apply(lambda d: json.dumps(d.get("matches", {}), ensure_ascii=False))
    # columnas limpias
    cols = ["username", "followers", "predicted_label", "score", "bio", "recent_captions", "scores_json", "matches_json"]
    df = df.reindex(columns=cols)
    df.to_csv(csv_path, index=False, encoding="utf-8")
    df.to_excel(xlsx_path, index=False)

    return json_path, csv_path, xlsx_path


def detect_profile_from_filename(p: Path):
    """
    Intenta inferir nombre de profile desde filename tipo followers_data_{profile}.json
    """
    m = re.search(r"followers_data_(.+?)\.json", p.name)
    if m:
        return m.group(1)
    # fallback: nombre del archivo sin extension
    return p.stem


def find_latest_results_dir():
    # Buscar archivos followers_data_*.json en ./results
    results = list(Path("results").glob("followers_data_*.json"))
    if not results:
        return None
    latest = max(results, key=lambda p: p.stat().st_mtime)
    return latest


def main():
    print("\nANALIZADOR DE BIOGRAFÍAS - Clasificación heurística\n")
    path_input = input("Ruta al JSON de resultados (ENTER para usar el último followers_data_*.json en ./results/): ").strip()
    if path_input:
        path = Path(path_input)
        if not path.exists():
            print("⚠️ Archivo no encontrado:", path)
            sys.exit(1)
    else:
        path = find_latest_results_dir()
        if not path:
            print("❌ No se encontró ningún followers_data_*.json en ./results/. Provee la ruta manualmente.")
            sys.exit(1)
        print("Usando archivo detectado:", path)

    data = load_json(path)
    # data puede ser lista de dicts
    if isinstance(data, dict) and "data" in data:
        records_input = data["data"]
    elif isinstance(data, list):
        records_input = data
    else:
        # intentar manejar dict de username -> info
        records_input = []
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, dict):
                    v["username"] = v.get("username", k)
                    records_input.append(v)

    results = []
    for item in records_input:
        username = item.get("username") or item.get("user") or None
        followers = item.get("followers")
        bio = item.get("bio") or ""
        recent_captions = item.get("recent_captions") or []

        predicted_label, score, detail = classify_profile(bio, recent_captions)
        results.append({
            "username": username,
            "followers": followers,
            "predicted_label": predicted_label,
            "score": round(score, 4),
            "bio": bio,
            "recent_captions": recent_captions,
            "detail": detail
        })

    profile_name = detect_profile_from_filename(path)
    out_dir = Path("results")
    j, c, x = save_outputs(profile_name, results, out_dir)

    print("\n✅ Análisis completado.")
    print(f"Archivos generados:\n  - {j}\n  - {c}\n  - {x}\n")
    print("Notas:")
    print(" - El análisis es heurístico. Ajusta KEYWORD_MAP para mejorar precisión.")
    print(" - Puedes cambiar WEIGHT_BIO, WEIGHT_CAPTIONS y SCORE_THRESHOLD en el script.\n")


if __name__ == "__main__":
    main()
