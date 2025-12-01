"""
Archivo: file_manager.py
Descripción: Guardado y carga de datos
"""

import json
from datetime import datetime
from config import RESULTS_DIR


def save_followers_txt(followers, profile):
    """Guarda followers en archivo de texto"""
    filename = RESULTS_DIR / f"followers_{profile}.txt"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"Followers de @{profile}\n")
        f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total: {len(followers)}\n")
        f.write("=" * 60 + "\n\n")
        f.write("\n".join(sorted(followers)))
    
    print(f"✅ Followers guardados en: {filename}")
    return filename


def save_followers_data_json(followers_data, profile):
    """Guarda datos de followers en JSON"""
    filename = RESULTS_DIR / f"followers_data_{profile}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(followers_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Datos JSON guardados en: {filename}")
    return filename
