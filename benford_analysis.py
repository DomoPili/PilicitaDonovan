"""
Archivo: benford_analysis.py
Descripción: Análisis de la Ley de Benford (incluye name, following, bio y captions en el Excel)
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
    Analiza datos con la Ley de Benford y genera gráfica y Excel detallado
    """
    print("\n" + "=" * 60)
    print("📊 ANÁLISIS LEY DE BENFORD")
    print("=" * 60)

    try:
        df = cargar_json_instagram(json_file)
    except Exception as e:
        print(f"❌ Error cargando JSON: {e}")
        return None

    possible_cols = [c for c in df.columns if "follow" in c.lower() and "ing" not in c.lower()]
    # Buscamos "followers" pero excluimos "following" para detectar la columna principal
    if not possible_cols:
        # Fallback por si la columna se llama diferente pero contiene números
        possible_cols = [c for c in df.columns if "follow" in c.lower()]

    if not possible_cols:
        print("⚠️ No se encontró columna de followers")
        return None
    
    # Usamos 'followers' como la columna de análisis
    follow_col = 'followers' if 'followers' in df.columns else possible_cols[0]

    # --- CONSTRUCCIÓN DEL DATAFRAME LIMPIO PARA EL EXCEL ---
    df_clean = pd.DataFrame()
    
    # 1. Username
    if 'username' in df.columns:
        df_clean["username"] = df["username"].astype(str)
    else:
        df_clean["username"] = df[df.columns[0]].astype(str)

    # 2. Name (Nombre real) - [NUEVO]
    df_clean["name"] = df["name"] if "name" in df.columns else None

    # 3. Followers (Seguidores)
    df_clean["followers"] = df[follow_col]

    # 4. Following (Seguidos) - [NUEVO]
    df_clean["following"] = df["following"] if "following" in df.columns else None

    # 5. Bio
    df_clean["bio"] = df["bio"] if "bio" in df.columns else None

    # 6. Recent Captions (formateado)
    if "recent_captions" in df.columns:
        def join_captions(x):
            if isinstance(x, list):
                # Une los textos con una barra vertical para que quepan en una celda de Excel
                return " | ".join([str(i).replace('\n', ' ').strip() for i in x if i is not None and str(i).strip() != ""])
            elif pd.isna(x):
                return None
            elif isinstance(x, str):
                return x
            return None
        df_clean["recent_captions"] = df["recent_captions"].apply(join_captions)
    else:
        df_clean["recent_captions"] = None

    # Calculamos el primer dígito para Benford (basado en followers)
    df_clean["primer_digito"] = df_clean["followers"].apply(primer_digito_valor)

    # --- CÁLCULO DE BENFORD ---
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

    # --- GUARDAR EXCEL ---
    excel_file = RESULTS_DIR / f"benford_{profile}.xlsx"
    
    # Ordenar columnas para que se vean bien en el Excel
    column_order = ["username", "name", "followers", "following", "primer_digito", "bio", "recent_captions"]
    # Asegurarnos de que solo pedimos columnas que existen
    final_cols = [c for c in column_order if c in df_clean.columns]
    
    with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
        df_clean[final_cols].to_excel(writer, sheet_name="followers_completo", index=False)
        comparacion.to_excel(writer, sheet_name="comparacion_benford", index=False)

        # Ajuste de ancho de columnas (cosmético para el profe)
        worksheet = writer.sheets['followers_completo']
        worksheet.column_dimensions['A'].width = 20  # Username
        worksheet.column_dimensions['B'].width = 25  # Name
        worksheet.column_dimensions['C'].width = 15  # Followers
        worksheet.column_dimensions['D'].width = 15  # Following
        worksheet.column_dimensions['F'].width = 40  # Bio
        worksheet.column_dimensions['G'].width = 50  # Captions

    print(f"✅ Excel generado: {excel_file}")

    # --- GENERAR GRÁFICA ---
    png_file = RESULTS_DIR / f"benford_{profile}.png"
    fig, ax = plt.subplots(figsize=(10, 6))

    bar_width = 0.35
    ax.bar(digitos - bar_width/2, comparacion["Frecuencia_Real_%"], width=bar_width, label="Datos Reales (%)", alpha=0.85, color='#4CAF50')
    ax.plot(digitos, comparacion["Benford_%"], marker="o", linewidth=2, label="Ley de Benford (%)", color='#FF5722')

    ax.set_title(f"Ley de Benford - @{profile}", fontsize=14, fontweight='bold')
    ax.set_xlabel("Primer dígito (Followers)", fontsize=12)
    ax.set_ylabel("Frecuencia (%)", fontsize=12)
    ax.set_xticks(digitos)
    ax.grid(alpha=0.3, linestyle='--')
    ax.legend(fontsize=10)

    # Añadir tabla pequeña con estadísticas en la gráfica
    stats_text = (
        f"Total Muestras: {total_validos}\n"
        f"Promedio Followers: {df_clean['followers'].mean():.0f}"
    )
    plt.text(0.95, 0.95, stats_text, transform=ax.transAxes, fontsize=9,
             verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    plt.tight_layout()
    fig.savefig(png_file, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"✅ Gráfica generada: {png_file}")
    print("=" * 60 + "\n")

    return {'excel': excel_file, 'png': png_file, 'comparacion': comparacion}