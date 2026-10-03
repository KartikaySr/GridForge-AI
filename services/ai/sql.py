"""Small SQL language, scoped source window, independent read-only DB capability."""

import hashlib
import json
import sqlite3
import time
from contextlib import closing
from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from edge.storage.repository import Repository
from services.ai.contracts import QueryRun

VIEWS: dict[str, list[str]] = {
    "ai_telemetry": ["row_id", "asset_id", "observed_at", "value_kw", "quality", "flags"],
    "ai_dispatch": ["command_id", "state", "observed_at"],
    "ai_savings": ["entry_id", "status", "currency", "amount", "observed_at"],
}
NODES = {
    "select",
    "column",
    "identifier",
    "alias",
    "from",
    "table",
    "where",
    "group",
    "order",
    "ordered",
    "limit",
    "literal",
    "eq",
    "neq",
    "gt",
    "gte",
    "lt",
    "lte",
    "and",
    "or",
    "not",
    "paren",
    "is",
    "null",
    "boolean",
    "count",
    "avg",
    "min",
    "max",
    "sum",
    "star",
}


class SQLRejected(ValueError):
    pass


def compile_query(sql: str, dialect: str = "sqlite") -> tuple[str, str]:
    if not sql.strip() or len(sql) > 4000 or "--" in sql or "/*" in sql:
        raise SQLRejected("SQL_NOT_ALLOWED")
    try:
        statements = sqlglot.parse(sql, read=dialect)
    except ParseError:
        raise SQLRejected("SQL_NOT_ALLOWED") from None
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise SQLRejected("SELECT_ONLY")
    tree = statements[0]
    nodes = list(tree.walk())
    if len(nodes) > 150 or any(node.key not in NODES for node in nodes):
        raise SQLRejected("SQL_STRUCTURE_NOT_ALLOWED")
    tables = list(tree.find_all(exp.Table))
    if len(tables) != 1 or tables[0].name not in VIEWS or tables[0].db or tables[0].catalog:
        raise SQLRejected("VIEW_NOT_ALLOWED")
    table = tables[0]
    if table.alias:
        raise SQLRejected("TABLE_ALIAS_NOT_ALLOWED")
    view = table.name
    aliases = {node.alias for node in tree.expressions if isinstance(node, exp.Alias)}
    for column in tree.find_all(exp.Column):
        if column.table or column.name not in set(VIEWS[view]) | aliases:
            raise SQLRejected("COLUMN_NOT_ALLOWED")
    for star in tree.find_all(exp.Star):
        if not isinstance(star.parent, exp.Count):
            raise SQLRejected("EXPLICIT_COLUMNS_REQUIRED")
    # Keep exact decimal monetary strings; no binary-float financial arithmetic.
    if view == "ai_savings" and any(
        isinstance(node, (exp.Sum, exp.Avg, exp.Min, exp.Max)) for node in nodes
    ):
        raise SQLRejected("FINANCIAL_AGGREGATION_NOT_ALLOWED")
    limit = tree.args.get("limit")
    if limit:
        value = limit.expression
        if (
            not isinstance(value, exp.Literal)
            or not value.is_int
            or not 1 <= int(value.this) <= 100
        ):
            raise SQLRejected("ROW_LIMIT_EXCEEDED")
    else:
        tree.set("limit", exp.Limit(expression=exp.Literal.number(100)))
    # Source replacement is created by code after validating all user AST nodes.
    # Scope precedes user filtering/aggregation; OR clauses cannot bypass it.
    marker = "?" if dialect == "sqlite" else "%s"
    relation = view if dialect == "sqlite" else f"ai_reporting.{view}"
    source = (
        f"(SELECT {', '.join(VIEWS[view])} FROM {relation} "
        f"WHERE org_id={marker} AND facility_id={marker} "
        "ORDER BY observed_at DESC LIMIT 1000) AS scoped_source"
    )
    source_marker = "scope_" + uuid4().hex
    table.replace(exp.Table(this=exp.Identifier(this=source_marker)))
    output = tree.sql(dialect=dialect)
    return output.replace(source_marker, source), view


def execute_local(repo: Repository, sql: str, org_id: UUID, facility_id: UUID) -> QueryRun:
    run = QueryRun(
        id=uuid4(),
        status="REJECTED",
        proposed_sql=sql,
        executed_sql=None,
        parameters=[],
        columns=[],
        rows=[],
        source_view=None,
        observed_at=datetime.now(UTC),
        error=None,
        result_digest=None,
    )
    try:
        compiled, view = compile_query(sql)
    except SQLRejected as exc:
        return run.model_copy(update={"error": str(exc)})
    run.executed_sql, run.source_view = compiled, view
    run.parameters = [str(org_id), str(facility_id)]
    deadline = time.monotonic() + 0.2
    try:
        with closing(sqlite3.connect(repo.read_uri, uri=True, timeout=0.1)) as conn:
            conn.execute("PRAGMA query_only=ON")
            conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 100)

            def authorize(
                action: int,
                arg1: str | None,
                arg2: str | None,
                database: str | None,
                source: str | None,
            ) -> int:
                if action == sqlite3.SQLITE_SELECT:
                    return sqlite3.SQLITE_OK
                if action == sqlite3.SQLITE_READ and (arg1 == view or source == view):
                    return sqlite3.SQLITE_OK
                if action == sqlite3.SQLITE_FUNCTION and arg2 in {
                    "count",
                    "avg",
                    "min",
                    "max",
                    "sum",
                    "json_extract",
                }:
                    return sqlite3.SQLITE_OK
                return sqlite3.SQLITE_DENY

            conn.set_authorizer(authorize)
            cursor = conn.execute(compiled, run.parameters)
            run.columns = [str(col[0]) for col in cursor.description or []]
            run.rows = [list(row) for row in cursor.fetchmany(100)]
            run.status = "SUCCEEDED"
            run.result_digest = hashlib.sha256(
                json.dumps([run.columns, run.rows], sort_keys=True).encode()
            ).hexdigest()
    except sqlite3.Error:
        run.status, run.error = "UNAVAILABLE", "QUERY_BUDGET_OR_DATABASE_UNAVAILABLE"
    return run
