"""Validation stricte d'un CSV : aucune conversion silencieuse des valeurs invalides."""

import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation

COLUMNS = ["sale_id", "date", "product", "category", "quantity", "unit_price"]
MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 10000


def parse_csv(data: bytes):
    if len(data) > MAX_BYTES:
        raise ValueError("Fichier trop volumineux : maximum 2 Mo.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Le fichier doit être encodé en UTF-8.") from exc
    reader = csv.DictReader(io.StringIO(text), strict=True)
    if reader.fieldnames != COLUMNS:
        raise ValueError("Colonnes attendues dans cet ordre : " + ", ".join(COLUMNS))
    valid, errors, seen = [], [], set()
    try:
        for index, raw in enumerate(reader, 2):
            if index > MAX_ROWS + 1:
                raise ValueError("Maximum 10 000 lignes par fichier.")
            row_errors = []
            if None in raw or any(v is None for v in raw.values()):
                row_errors.append("Nombre de champs incorrect")
            row = {key: (raw.get(key) or "").strip() for key in COLUMNS}
            for key in ["sale_id", "product", "category"]:
                if not row[key] or len(row[key]) > 120:
                    row_errors.append(f"{key} : texte requis, maximum 120 caractères")
            try:
                parsed_date = date.fromisoformat(row["date"])
                if parsed_date.isoformat() != row["date"]:
                    raise ValueError
            except ValueError:
                row_errors.append("date : format YYYY-MM-DD requis")
            try:
                quantity = int(row["quantity"])
                if not row["quantity"].isascii() or not row["quantity"].isdigit() or not 1 <= quantity <= 100000:
                    raise ValueError
            except ValueError:
                row_errors.append("quantity : entier entre 1 et 100 000 requis")
            try:
                price = Decimal(row["unit_price"])
                if not price.is_finite() or price <= 0 or price > 1000000 or price != price.quantize(Decimal("0.01")):
                    raise ValueError
            except (InvalidOperation, ValueError):
                row_errors.append("unit_price : montant positif, maximum 1 000 000 et deux décimales")
            if row["sale_id"] in seen:
                row_errors.append("sale_id : doublon dans le fichier")
            seen.add(row["sale_id"])
            if row_errors:
                errors.append({"line": index, "sale_id": row["sale_id"], "reason": " ; ".join(row_errors)})
            else:
                valid.append({**row, "date": parsed_date, "quantity": quantity, "unit_price": price})
    except csv.Error as exc:
        raise ValueError("CSV mal formé.") from exc
    if not valid and not errors:
        raise ValueError("Le fichier ne contient aucune vente.")
    return valid, errors
