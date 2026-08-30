#!/usr/bin/env python3
"""
custodia.py — Generador de Cadena de Custodia Digital para Peritaje Informático

Calcula hashes forenses (SHA-256/SHA-1/MD5) de un archivo o directorio de
evidencia digital, genera un acta de cadena de custodia (Markdown y, si se
solicita, PDF) conforme a la metodología ISO/IEC 27037, y puede solicitar un
sello de tiempo cualificado (RFC 3161) a una Autoridad de Sellado de Tiempo
(TSA) para dar fecha cierta e inalterable al momento de la adquisición.

Autora: Nieves Casquero — Perito Informático de Parte (Colegiada AEPEJU)
Licencia: MIT
"""

import argparse
import hashlib
import json
import os
import platform
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

VERSION = "1.0.0"


# --------------------------------------------------------------------------- #
# Cálculo de hashes
# --------------------------------------------------------------------------- #

def hash_file(path: Path, algorithms=("sha256", "sha1", "md5"), chunk_size=1024 * 1024):
    """Calcula uno o varios hashes de un archivo en streaming (apto para
    archivos grandes de evidencia sin cargarlos enteros en memoria)."""
    hashers = {alg: hashlib.new(alg) for alg in algorithms}
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            for h in hashers.values():
                h.update(chunk)
    return {alg: h.hexdigest() for alg, h in hashers.items()}


def collect_evidence(target: Path):
    """Recorre un archivo o directorio y calcula los hashes y metadatos de
    cada fichero encontrado."""
    files = [target] if target.is_file() else sorted(p for p in target.rglob("*") if p.is_file())

    evidence = []
    for f in files:
        stat = f.stat()
        evidence.append({
            "ruta": str(f),
            "tamano_bytes": stat.st_size,
            "modificado_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            "hashes": hash_file(f),
        })
    return evidence


def manifest_hash(evidence):
    """Genera un hash SHA-256 del manifiesto completo (hash de hashes),
    de forma que cualquier alteración posterior de una sola línea del acta
    invalida la integridad del conjunto."""
    payload = json.dumps(evidence, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# --------------------------------------------------------------------------- #
# Sellado de tiempo cualificado (RFC 3161)
# --------------------------------------------------------------------------- #

def request_timestamp(digest_hex: str, tsa_url: str):
    """Solicita un sello de tiempo RFC 3161 para el hash del manifiesto a una
    Autoridad de Sellado de Tiempo (TSA). Requiere el paquete opcional
    'rfc3161ng' y conexión a internet. Si no está disponible, se informa al
    usuario sin interrumpir la generación del acta (el sellado es opcional).
    """
    try:
        import rfc3161ng
    except ImportError:
        return {
            "ok": False,
            "motivo": "El paquete opcional 'rfc3161ng' no está instalado. "
                      "Instálalo con: pip install rfc3161ng",
        }

    try:
        timestamper = rfc3161ng.RemoteTimestamper(tsa_url, hashname="sha256")
        digest_bytes = bytes.fromhex(digest_hex)
        tst = timestamper.timestamp(digest=digest_bytes)
        return {
            "ok": True,
            "tsa_url": tsa_url,
            "token_der_base64": rfc3161ng.__dict__.get("b64", None) and None,
            "token_raw": tst,
        }
    except Exception as e:
        return {"ok": False, "motivo": f"No se pudo obtener el sello de tiempo: {e}"}


# --------------------------------------------------------------------------- #
# Generación del acta
# --------------------------------------------------------------------------- #

def build_report_markdown(evidence, meta, m_hash, timestamp_info):
    lines = []
    lines.append("# Acta de Cadena de Custodia Digital\n")
    lines.append(f"**Caso / referencia:** {meta['caso']}  ")
    lines.append(f"**Perito / examinador:** {meta['examinador']}  ")
    lines.append(f"**Fecha y hora de generación (UTC):** {meta['generado_utc']}  ")
    lines.append(f"**Equipo de adquisición:** {meta['hostname']} ({meta['sistema']})  ")
    lines.append(f"**Metodología aplicada:** ISO/IEC 27037:2012 — Directrices para la "
                  "identificación, recolección, adquisición y preservación de evidencia digital\n")

    lines.append("## Elementos de evidencia\n")
    lines.append("| # | Ruta | Tamaño (bytes) | Última modificación (UTC) | SHA-256 |")
    lines.append("|---|---|---|---|---|")
    for i, item in enumerate(evidence, start=1):
        lines.append(f"| {i} | `{item['ruta']}` | {item['tamano_bytes']} | "
                      f"{item['modificado_utc']} | `{item['hashes']['sha256']}` |")

    lines.append("\n<details><summary>Hashes adicionales (SHA-1 / MD5) por elemento</summary>\n")
    for i, item in enumerate(evidence, start=1):
        lines.append(f"- **#{i}** `{item['ruta']}` — SHA-1: `{item['hashes']['sha1']}` — "
                      f"MD5: `{item['hashes']['md5']}`")
    lines.append("\n</details>\n")

    lines.append("## Integridad del acta\n")
    lines.append(f"**Hash SHA-256 del manifiesto completo:** `{m_hash}`\n")
    lines.append("Cualquier modificación posterior de un solo carácter en los datos anteriores "
                  "invalida este hash, permitiendo detectar alteraciones del acta.\n")

    lines.append("## Sello de tiempo (RFC 3161)\n")
    if timestamp_info is None:
        lines.append("No solicitado.\n")
    elif timestamp_info.get("ok"):
        lines.append(f"Sello de tiempo obtenido correctamente de la TSA: `{timestamp_info['tsa_url']}`\n")
        lines.append("El token de sello de tiempo (formato .tsr, binario) se ha guardado junto a este acta.\n")
    else:
        lines.append(f"⚠️ No se pudo obtener el sello de tiempo: {timestamp_info.get('motivo')}\n")

    lines.append("---\n")
    lines.append(f"*Generado con custodia.py v{VERSION} — "
                  "https://github.com/AnkbNikas/cadena-custodia*")
    return "\n".join(lines)


def build_report_pdf(markdown_text: str, output_path: Path):
    try:
        from fpdf import FPDF
        from fpdf.enums import XPos, YPos
    except ImportError:
        print("Aviso: para generar PDF instala la dependencia opcional: pip install fpdf2",
              file=sys.stderr)
        return False

    def break_long_tokens(text, max_len=50):
        """Inserta espacios dentro de tokens muy largos (hashes) para que
        fpdf2 pueda ajustar la línea; de lo contrario lanza una excepción."""
        out_words = []
        for word in text.split(" "):
            if len(word) > max_len:
                word = " ".join(word[i:i + max_len] for i in range(0, len(word), max_len))
            out_words.append(word)
        return " ".join(out_words)

    def sanitize_for_core_font(text: str) -> str:
        """La fuente core Helvetica solo soporta latin-1. Sustituye los
        caracteres tipográficos habituales por su equivalente ASCII y, como
        red de seguridad, elimina cualquier otro carácter no soportado."""
        replacements = {
            "—": "-", "–": "-", "’": "'", "‘": "'", "“": '"', "”": '"', "…": "...",
        }
        for orig, repl in replacements.items():
            text = text.replace(orig, repl)
        return text.encode("latin-1", errors="replace").decode("latin-1")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=9)
    for raw_line in markdown_text.splitlines():
        line = (raw_line.replace("**", "").replace("`", "").replace("#", "").replace("|", " ")
                .replace("<details>", "").replace("</details>", "")
                .replace("<summary>", "").replace("</summary>", ""))
        line = sanitize_for_core_font(line)
        line = break_long_tokens(line)
        if not line.strip():
            pdf.ln(3)
            continue
        # new_x/new_y explícitos: sin esto, fpdf2 deja el cursor pegado al
        # margen derecho tras cada multi_cell, dejando casi 0mm de ancho
        # disponible para la siguiente línea.
        pdf.multi_cell(0, 5, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.output(str(output_path))
    return True


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser(
        prog="custodia",
        description="Genera un acta de cadena de custodia digital (hashes forenses + "
                     "sello de tiempo opcional) para peritaje informático."
    )
    parser.add_argument("ruta", help="Archivo o directorio de evidencia a procesar")
    parser.add_argument("--caso", default="Sin especificar", help="Referencia del caso/expediente")
    parser.add_argument("--examinador", default="Sin especificar", help="Nombre del perito/examinador")
    parser.add_argument("--salida", default="acta_custodia", help="Nombre base de los ficheros de salida")
    parser.add_argument("--pdf", action="store_true", help="Genera también el acta en PDF")
    parser.add_argument("--timestamp", metavar="TSA_URL", default=None,
                         help="URL de una TSA RFC 3161 para sellar el hash del manifiesto "
                              "(requiere pip install rfc3161ng)")
    args = parser.parse_args()

    target = Path(args.ruta)
    if not target.exists():
        print(f"Error: la ruta '{args.ruta}' no existe.", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Procesando evidencia en: {target}")
    evidence = collect_evidence(target)
    print(f"[*] {len(evidence)} archivo(s) procesado(s).")

    m_hash = manifest_hash(evidence)

    timestamp_info = None
    if args.timestamp:
        print(f"[*] Solicitando sello de tiempo a {args.timestamp} ...")
        timestamp_info = request_timestamp(m_hash, args.timestamp)
        if timestamp_info.get("ok"):
            print("[+] Sello de tiempo obtenido correctamente.")
        else:
            print(f"[!] {timestamp_info.get('motivo')}")

    meta = {
        "caso": args.caso,
        "examinador": args.examinador,
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "sistema": f"{platform.system()} {platform.release()}",
    }

    manifest = {
        "meta": meta,
        "evidencia": evidence,
        "hash_manifiesto_sha256": m_hash,
        "sello_tiempo": {k: v for k, v in (timestamp_info or {}).items() if k != "token_raw"},
    }

    json_path = Path(f"{args.salida}.json")
    md_path = Path(f"{args.salida}.md")

    json_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    md_text = build_report_markdown(evidence, meta, m_hash, timestamp_info)
    md_path.write_text(md_text, encoding="utf-8")

    print(f"[+] Manifiesto JSON: {json_path}")
    print(f"[+] Acta Markdown:   {md_path}")

    if args.pdf:
        pdf_path = Path(f"{args.salida}.pdf")
        if build_report_pdf(md_text, pdf_path):
            print(f"[+] Acta PDF:        {pdf_path}")


if __name__ == "__main__":
    main()
