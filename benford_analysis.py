"""
Archivo: benford_analysis.py
Descripción: Análisis de la Ley de Benford (incluye bio y captions en el Excel)
"""

import json
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from config import RESULTS_DIR


def cargar_json_instagram(ruta):
    """Carga JSON con múltiples formatos"""
    with open(ruta, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return pd.DataFrame(data)

    if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
        return pd.DataFrame(data["data"])

    for key in data:
        if isinstance(data[key], list) and len(data[key]) > 0 and isinstance(data[key][0], dict):
            return pd.DataFrame(data[key])

    if isinstance(data, dict):
        return pd.DataFrame([data])

    raise ValueError("⚠️ No se pudo interpretar la estructura del JSON.")


def primer_digito_valor(valor):
    """Extrae el primer dígito de un valor"""
    if pd.isna(valor):
        return np.nan
    s = str(valor).strip().replace(",", "")
    m = re.search(r"[1-9]", s)
    if m:
        return int(m.group(0))
    return np.nan


def analizar_benford(json_file, profile):
    """
    Analiza datos con la Ley de Benford y genera gráfica
    """
    print("\n" + "=" * 60)
    print("📊 ANÁLISIS LEY DE BENFORD")
    print("=" * 60)

    df = cargar_json_instagram(json_file)

    possible_cols = [c for c in df.columns if "follow" in c.lower()]
    if not possible_cols:
        print("⚠️ No se encontró columna de followers")
        return None
    follow_col = possible_cols[0]

    # Preparar df_clean con columnas adicionales
    df_clean = pd.DataFrame()
    if 'username' in df.columns:
        df_clean["username"] = df["username"].astype(str)
    else:
        df_clean["username"] = df[df.columns[0]].astype(str)

    df_clean["followers"] = df[follow_col]

    # bio
    df_clean["bio"] = df["bio"] if "bio" in df.columns else None

    # recent_captions -> join list to single cell for Excel (separator " | ")
    if "recent_captions" in df.columns:
        def join_captions(x):
            if isinstance(x, list):
                return " | ".join([str(i) for i in x if i is not None and str(i).strip() != ""])
            elif pd.isna(x):
                return None
            elif isinstance(x, str):
                return x
            return None
        df_clean["recent_captions"] = df["recent_captions"].apply(join_captions)
    else:
        df_clean["recent_captions"] = None

    df_clean["primer_digito"] = df_clean["followers"].apply(primer_digito_valor)

    # Benford
    digitos = np.arange(1, 10)
    conteos = df_clean["primer_digito"].value_counts().reindex(digitos, fill_value=0)
    total_validos = conteos.sum()

    if total_validos == 0:
        print("⚠️ No hay datos válidos para aplicar Benford")
        return None

    porcentaje_real = (conteos / total_validos) * 100
    porcentaje_benford = np.array([np.log10(1 + 1/d) * 100 for d in digitos])

    comparacion = pd.DataFrame({
        "Dígito": digitos,
        "Conteo": conteos.values,
        "Frecuencia_Real_%": porcentaje_real.round(3).values,
        "Benford_%": porcentaje_benford.round(3),
        "Diferencia_%": (porcentaje_real - porcentaje_benford).round(3)
    })

    # Guardar Excel
    excel_file = RESULTS_DIR / f"benford_{profile}.xlsx"
    with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
        df_clean.to_excel(writer, sheet_name="followers_completo", index=False)
        comparacion.to_excel(writer, sheet_name="comparacion_benford", index=False)

    print(f"✅ Excel generado: {excel_file}")

    # Gráfica
    png_file = RESULTS_DIR / f"benford_{profile}.png"
    fig, ax = plt.subplots(figsize=(10, 6))

    bar_width = 0.35
    ax.bar(digitos - bar_width/2, comparacion["Frecuencia_Real_%"], width=bar_width, label="Datos Reales (%)", alpha=0.85)
    ax.plot(digitos, comparacion["Benford_%"], marker="o", linewidth=2, label="Ley de Benford (%)")

    ax.set_title(f"Ley de Benford - @{profile}", fontsize=14, fontweight='bold')
    ax.set_xlabel("Primer dígito", fontsize=12)
    ax.set_ylabel("Frecuencia (%)", fontsize=12)
    ax.set_xticks(digitos)
    ax.grid(alpha=0.3, linestyle='--')
    ax.legend(fontsize=10)

    plt.tight_layout()
    fig.savefig(png_file, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"✅ Gráfica generada: {png_file}")
    print("=" * 60 + "\n")

    return {'excel': excel_file, 'png': png_file, 'comparacion': comparacion}
