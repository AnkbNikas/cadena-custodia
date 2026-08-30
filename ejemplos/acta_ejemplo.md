# Acta de Cadena de Custodia Digital

**Caso / referencia:** EXP-2026-014 (ejemplo ilustrativo)  
**Perito / examinador:** Nieves Casquero  
**Fecha y hora de generación (UTC):** 2026-08-30T09:25:41.274555+00:00  
**Equipo de adquisición:** vm (Linux 6.18.44-fc-v22)  
**Metodología aplicada:** ISO/IEC 27037:2012 — Directrices para la identificación, recolección, adquisición y preservación de evidencia digital

## Elementos de evidencia

| # | Ruta | Tamaño (bytes) | Última modificación (UTC) | SHA-256 |
|---|---|---|---|---|
| 1 | `ejemplos/evidencia_demo/correo_sospechoso.eml` | 91 | 2026-08-30T09:25:41.235201+00:00 | `26c59feb99c412130079feac742aeef8057fe5a1587339c6a239401d214cf535` |
| 2 | `ejemplos/evidencia_demo/log_acceso.txt` | 79 | 2026-08-30T09:25:41.235201+00:00 | `013ccb2efb0c6794d164eb7aa09031d667b2732842320e7adcf258188cee9a59` |

<details><summary>Hashes adicionales (SHA-1 / MD5) por elemento</summary>

- **#1** `ejemplos/evidencia_demo/correo_sospechoso.eml` — SHA-1: `891225bd5e9cb2bd0c990c018b4e7031e7607178` — MD5: `0ea5b2322e5e01cdf8e85d3754fcc5ee`
- **#2** `ejemplos/evidencia_demo/log_acceso.txt` — SHA-1: `356baec536a1c8c7217a591c6eaa5f6579078358` — MD5: `6eb972f5aa841a81e0560acba2d25b6a`

</details>

## Integridad del acta

**Hash SHA-256 del manifiesto completo:** `ff05e88bab6c896d62f91a1a62fb3fb3aee97822dfdbff1021a583180d962df8`

Cualquier modificación posterior de un solo carácter en los datos anteriores invalida este hash, permitiendo detectar alteraciones del acta.

## Sello de tiempo (RFC 3161)

No solicitado.

---

*Generado con custodia.py v1.0.0 — https://github.com/AnkbNikas/cadena-custodia*