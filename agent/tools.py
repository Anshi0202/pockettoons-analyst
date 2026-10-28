"""
tools.py - the only way the agent touches the data.

    get_schema()      table definitions (incl. the column notes from the DDL), row counts, date ranges
    run_sql(query)    one read-only SELECT; returns a small Markdown table, or an error message the
                      model can read and fix

Safety does not rely on the prompt. It is layered in code:
  1. The file is opened with SQLite's `mode=ro` URI, so writes are impossible at the driver level.
  2. `PRAGMA query_only = ON` as a second lock.
  3. Only a single SELECT / WITH statement is accepted (clear message instead of a cryptic one).
  4. A progress handler aborts any query that runs longer than QUERY_TIMEOUT_S.
  5. At most MAX_ROWS rows and MAX_CELL_CHARS per cell go back to the model (protects the context
     window and pushes the model to aggregate in SQL instead of reading raw rows).

Errors are returned as text, never raised, so a bad query becomes something the model can learn
from on its next step instead of crashing the run.
"""

import os
import re
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("PT_DB", ROOT / "data" / "pockettoons.db"))

MAX_ROWS = 100           # rows returned to the model per query
MAX_CELL_CHARS = 80      # long text cells are cut
QUERY_TIMEOUT_S = 30     # wall-clock limit per query

ALLOWED_FIRST_WORDS = {"SELECT", "WITH"}

# Tool definitions (provider-neutral JSON Schema; agent.py wraps them for the OpenAI API).
TOOL_SPECS = [
    {
        "name": "get_schema",
        "description": (
            "Describe the database: every table with its columns and column notes, row counts, "
            "and the date range each table covers. Call this before writing any SQL."
        ),
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    },
    {
        "name": "run_sql",
        "description": (
            "Run ONE read-only SQLite SELECT (or WITH ... SELECT) query and get the result as a table. "
            f"At most {MAX_ROWS} rows are returned, so aggregate in SQL rather than pulling raw rows. "
            "If the query fails you get the error message back; fix the query and try again."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "A single SQLite SELECT statement."},
                "purpose": {
                    "type": "string",
                    "description": "One sentence: what this query checks and which hypothesis or question it serves.",
                },
            },
            "required": ["query", "purpose"],
            "additionalProperties": False,
        },
    },
]

_LEADING_COMMENTS = re.compile(r"^(?:\s+|--[^\n]*(?:\n|$)|/\*.*?\*/)*", re.S)


def _first_word(sql):
    body = _LEADING_COMMENTS.sub("", sql, count=1)
    m = re.match(r"[A-Za-z]+", body)
    return m.group(0).upper() if m else ""


def _fmt(v):
    if v is None:
        return "NULL"
    if isinstance(v, float):
        if v.is_integer() and abs(v) < 1e15:
            return str(int(v))
        return repr(round(v, 4))
    s = str(v).replace("|", "\\|").replace("\n", " ")
    return s if len(s) <= MAX_CELL_CHARS else s[: MAX_CELL_CHARS - 3] + "..."


def _table(cols, rows):
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(_fmt(v) for v in r) + " |" for r in rows]
    return "\n".join(lines)


class SQLTools:
    """One read-only connection per agent run."""

    def __init__(self, db_path=None, timeout_s=QUERY_TIMEOUT_S, max_rows=MAX_ROWS):
        path = Path(db_path or DB_PATH).resolve()
        if not path.exists():
            raise FileNotFoundError(
                f"Database not found at {path}. Build it first with: python data/generate.py"
            )
        self.path = path
        self.timeout_s = timeout_s
        self.max_rows = max_rows
        # as_uri() gives file:///C:/... on Windows and file:///home/... on Linux; both work with uri=True
        self.con = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, check_same_thread=False)
        self.con.execute("PRAGMA query_only = ON")
        self._schema = None

    def close(self):
        self.con.close()

    # ------------------------------------------------------------------ get_schema
    def get_schema(self):
        if self._schema is not None:
            return self._schema
        con = self.con
        tables = con.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        parts = [
            f"Database: SQLite file {self.path.name}. Dates are TEXT 'YYYY-MM-DD'.",
            "Column notes after '--' come from the table definitions.",
        ]
        for name, ddl in tables:
            n = con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            cols = [r[1] for r in con.execute(f'PRAGMA table_info("{name}")')]
            ranges = []
            for c in cols:
                if c == "date" or c.endswith("_date"):
                    lo, hi = con.execute(f'SELECT MIN("{c}"), MAX("{c}") FROM "{name}"').fetchone()
                    ranges.append(f"{c}: {lo} to {hi}")
            header = f"\n## {name}  ({n:,} rows" + (f"; {'; '.join(ranges)}" if ranges else "") + ")"
            parts += [header, ddl.strip()]
        self._schema = "\n".join(parts)
        return self._schema

    # ------------------------------------------------------------------ run_sql
    def run_sql(self, query):
        """Returns (text_for_model, meta). meta has ok/rows/truncated/ms/error for logging."""
        sql = (query or "").strip()
        meta = {"ok": False, "rows": 0, "truncated": False, "ms": 0, "error": None}
        if not sql:
            meta["error"] = "empty query"
            return "Error: empty query.", meta
        first = _first_word(sql)
        if first not in ALLOWED_FIRST_WORDS:
            meta["error"] = f"blocked statement type: {first or '?'}"
            return (
                f"Error: only read-only SELECT / WITH queries are allowed (got '{first or '?'}'). "
                "The database is read-only.", meta
            )

        deadline = time.monotonic() + self.timeout_s
        self.con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
        t0 = time.monotonic()
        try:
            cur = self.con.execute(sql)
            if cur.description is None:
                meta["error"] = "statement returned no result set"
                return "Error: the statement returned no result set. Use a SELECT.", meta
            cols = [d[0] for d in cur.description]
            rows = cur.fetchmany(self.max_rows + 1)
        except sqlite3.OperationalError as e:
            msg = str(e)
            if "interrupted" in msg:
                meta["error"] = "timeout"
                return (
                    f"Error: query cancelled after {self.timeout_s}s. Simplify it: filter dates early, "
                    "pre-aggregate in a CTE, and avoid correlated subqueries over large tables "
                    "(sessions, content_views).", meta
                )
            meta["error"] = msg
            hint = " Check names with get_schema()." if "no such" in msg else ""
            return f"SQL error: {msg}.{hint}", meta
        except (sqlite3.DatabaseError, sqlite3.Warning, sqlite3.ProgrammingError) as e:
            meta["error"] = str(e)
            return f"SQL error: {e}", meta
        finally:
            self.con.set_progress_handler(None, 0)
            meta["ms"] = int((time.monotonic() - t0) * 1000)

        truncated = len(rows) > self.max_rows
        rows = rows[: self.max_rows]
        meta.update(ok=True, rows=len(rows), truncated=truncated)
        if not rows:
            return (
                f"0 rows ({meta['ms']} ms). Nothing matched. If you filtered on a text value, "
                "check the valid values with SELECT DISTINCT.", meta
            )
        note = (
            f"\nShowing the first {self.max_rows} rows only; the query returned more. "
            "Aggregate further or add ORDER BY + LIMIT." if truncated else ""
        )
        label = "1 row" if len(rows) == 1 else f"{len(rows)} rows"
        return f"{label} ({meta['ms']} ms)\n{_table(cols, rows)}{note}", meta
