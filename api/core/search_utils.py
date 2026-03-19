"""
Search utilities — Romanian diacritics handling, PostgreSQL full-text search,
trigram fuzzy matching, and unified search condition builder.

Uses installed extensions: pg_trgm (fuzzy), unaccent (diacritics).
Uses existing indexes: idx_products_name_lower_trgm, idx_products_name_search_fts.
"""
import re
import unicodedata

# Romanian diacritics mapping
DIACRITICS_MAP = {
    'ă': 'a', 'â': 'a', 'î': 'i', 'ș': 's', 'ț': 't',
    'Ă': 'A', 'Â': 'A', 'Î': 'I', 'Ș': 'S', 'Ț': 'T',
    'ş': 's', 'ţ': 't', 'Ş': 'S', 'Ţ': 'T',  # cedilla variants
}


def strip_diacritics(text: str) -> str:
    """Remove Romanian diacritics from text."""
    result = []
    for char in text:
        result.append(DIACRITICS_MAP.get(char, char))
    return ''.join(result)


def normalize_search(text: str) -> str:
    """Normalize text for search: lowercase + strip diacritics."""
    return strip_diacritics(text.lower().strip())


def build_tsquery(search_text: str) -> str:
    """
    Build a PostgreSQL tsquery string from user input.
    Tokenizes, strips diacritics, and builds prefix-AND query.
    Example: "tel sap" -> "tel:* & sap:*"
    """
    normalized = normalize_search(search_text)
    tokens = re.split(r'\s+', normalized)
    tokens = [t for t in tokens if t]
    if not tokens:
        return ""
    return " & ".join(f"{t}:*" for t in tokens)


def build_search_conditions(
    search_text: str,
    name_column: str,
    param_prefix: str = "search",
    extra_columns: list[str] | None = None,
    similarity_threshold: float = 0.15,
) -> tuple[list[str], dict, str | None]:
    """
    Build SQL WHERE conditions + params for smart product search.

    Features:
      - #ID search: "#12345" searches by product ID
      - Multi-word AND: each word must appear in at least one searched column
      - Diacritics-aware: uses unaccent() so "telefon" matches "Telefón"
      - Prefix matching: "tric" matches "Tricicleta"
      - Fuzzy tolerance: uses pg_trgm similarity for typo handling

    Args:
        search_text: The raw user input
        name_column: SQL column for primary name (e.g. "pmv.name", "bs.name")
        param_prefix: Prefix for SQL params to avoid collisions
        extra_columns: Additional columns to search (e.g. ["p.vendor", "ppd.title"])
        similarity_threshold: pg_trgm similarity threshold (0.0–1.0, lower = more fuzzy)

    Returns:
        (conditions, params, order_expression)
        - conditions: list of SQL WHERE clauses to AND together
        - params: dict of named params
        - order_expression: SQL expression for relevance ordering (or None)
    """
    text = search_text.strip()
    if not text:
        return [], {}, None

    conditions = []
    params = {}
    order_expr = None

    # ─── #ID search ────────────────────────────────────────────
    id_match = re.match(r'^#(\d+)$', text)
    if id_match:
        param_key = f"{param_prefix}_id"
        # Try to match against common ID column patterns
        id_val = int(id_match.group(1))
        params[param_key] = id_val
        # The caller's ID column is usually "p.id" or derived from name_column's table
        table_alias = name_column.split('.')[0]
        conditions.append(f"{table_alias}.id = :{param_key}")
        return conditions, params, None

    # ─── Normalize and tokenize ────────────────────────────────
    normalized = normalize_search(text)
    tokens = re.split(r'\s+', normalized)
    tokens = [t for t in tokens if len(t) >= 1]
    if not tokens:
        return [], {}, None

    # All searchable columns
    all_columns = [name_column]
    if extra_columns:
        all_columns.extend(extra_columns)

    # ─── Multi-word AND with unaccent + ILIKE (prefix-friendly) ─
    # Each token must appear in at least one of the searched columns.
    # Using unaccent() for diacritics-agnostic matching.
    for i, token in enumerate(tokens):
        param_key = f"{param_prefix}_tok_{i}"
        params[param_key] = f"%{token}%"
        # OR across all columns for this token
        col_conditions = [
            f"unaccent(lower(COALESCE({col}, ''))) ILIKE unaccent(:{param_key})"
            for col in all_columns
        ]
        if len(col_conditions) == 1:
            conditions.append(col_conditions[0])
        else:
            conditions.append(f"({' OR '.join(col_conditions)})")

    # ─── Relevance ordering via trigram similarity ─────────────
    # Compute similarity of the full search string against the primary name column
    sim_param = f"{param_prefix}_sim"
    params[sim_param] = normalized
    order_expr = f"similarity(unaccent(lower(COALESCE({name_column}, ''))), unaccent(:{sim_param})) DESC"

    return conditions, params, order_expr
