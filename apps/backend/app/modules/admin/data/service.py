"""Queries, validation and serialisation for the generic data admin.

Reads and writes use SQLAlchemy Core on the request's connection, so database
semantics apply exactly: ``ON DELETE`` rules, check constraints, unique indexes and the
immutability triggers. Database errors are translated into field-level validation
errors where the failing column is known (unique, not-null, foreign-key violations).
"""

import json
import re
import uuid
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import (
    ColumnElement,
    RowMapping,
    Select,
    String,
    and_,
    asc,
    cast,
    delete,
    desc,
    false,
    func,
    insert,
    or_,
    select,
    text,
    tuple_,
    update,
)
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.core.security import generate_token, hash_password_async, hash_token
from app.infrastructure.redis import cache_delete
from app.modules.admin.data.registry import APPEND_ONLY, AdminModel, FieldSpec, get_model, registry

PK_SEPARATOR = ","
LOOKUP_LIMIT = 20
# Query-string lookups, as in Django: ``?status=PAID``, ``?total__gte=100``.
LOOKUPS = ("exact", "in", "gte", "lte", "gt", "lt", "icontains", "isnull")
_datetime = TypeAdapter(datetime)


# -- model resolution -------------------------------------------------------------------


def resolve(key: str) -> AdminModel:
    admin = get_model(key)
    if admin is None:
        raise NotFound(f"Unknown model {key!r}.", code="model_not_found")
    return admin


def require(admin: AdminModel, action: str) -> None:
    allowed = {"add": admin.can_add, "change": admin.can_change, "delete": admin.can_delete}[action]
    if not allowed:
        raise PermissionDenied(f"Records in {admin.key} cannot be {action}ed here.", code=f"model_{action}_disabled")


# -- primary keys -----------------------------------------------------------------------


def pk_string(admin: AdminModel, row: RowMapping) -> str:
    return PK_SEPARATOR.join(str(row[name]) for name in admin.pk)


def parse_pk(admin: AdminModel, raw: str) -> tuple[Any, ...]:
    parts = raw.split(PK_SEPARATOR)
    if len(parts) != len(admin.pk):
        raise NotFound("Record not found.")
    values: list[Any] = []
    for name, part in zip(admin.pk, parts, strict=True):
        try:
            values.append(_coerce(admin.by_name[name], part))
        except ValueError as exc:
            raise NotFound("Record not found.") from exc
    return tuple(values)


def pk_clause(admin: AdminModel, values: tuple[Any, ...]) -> ColumnElement[bool]:
    return and_(*(admin.table.c[name] == value for name, value in zip(admin.pk, values, strict=True)))


def pks_clause(admin: AdminModel, raw: Sequence[str]) -> ColumnElement[bool]:
    keys = [parse_pk(admin, r) for r in raw]
    if not keys:
        return false()
    if len(admin.pk) == 1:
        return admin.table.c[admin.pk[0]].in_([k[0] for k in keys])
    return tuple_(*(admin.table.c[n] for n in admin.pk)).in_(keys)


# -- values -----------------------------------------------------------------------------


def serialize(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def row_values(admin: AdminModel, row: RowMapping) -> dict[str, Any]:
    return {f.name: serialize(row[f.name]) for f in admin.fields}


def _coerce(spec: FieldSpec, raw: Any) -> Any:
    """Convert one JSON / query-string value to the column's Python type (``ValueError`` if invalid)."""
    kind = spec.kind
    if kind == "uuid":
        return raw if isinstance(raw, uuid.UUID) else uuid.UUID(str(raw))
    if kind in ("integer", "money"):
        if isinstance(raw, bool) or (isinstance(raw, float) and not raw.is_integer()):
            raise ValueError("Enter a whole number.")
        try:
            return int(str(raw).strip()) if isinstance(raw, str) else int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("Enter a whole number.") from exc
    if kind == "decimal":
        try:
            number = Decimal(str(raw).strip())
        except InvalidOperation as exc:
            raise ValueError("Enter a number.") from exc
        if not number.is_finite():
            raise ValueError("Enter a number.")
        return number
    if kind == "float":
        try:
            return float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("Enter a number.") from exc
    if kind == "boolean":
        if isinstance(raw, bool):
            return raw
        text = str(raw).strip().lower()
        if text in ("true", "1", "yes"):
            return True
        if text in ("false", "0", "no"):
            return False
        raise ValueError("Enter true or false.")
    if kind == "datetime":
        try:
            value = _datetime.validate_python(raw)
        except ValidationError as exc:
            raise ValueError("Enter a valid date and time.") from exc
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if kind == "json":
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError("Enter valid JSON.") from exc
        return raw
    # string / text
    if not isinstance(raw, str):
        raise ValueError("Enter text.")
    if spec.max_length is not None and len(raw) > spec.max_length:
        raise ValueError(f"Ensure this value has at most {spec.max_length} characters.")
    if spec.choices is not None and raw not in spec.choices:
        raise ValueError(f"Select one of: {', '.join(spec.choices)}.")
    return raw


def _issue(name: str, msg: str, type_: str = "value_error") -> dict[str, Any]:
    return {"loc": ["body", name], "msg": msg, "type": type_}


async def parse_payload(admin: AdminModel, payload: Mapping[str, Any], *, creating: bool) -> dict[str, Any]:
    """Validate a create / change payload and return column values (only those supplied)."""
    fields = admin.by_name
    issues: list[dict[str, Any]] = []
    values: dict[str, Any] = {}
    password_column = admin.config.password_column
    for name, raw in payload.items():
        if name == "password" and password_column:
            if raw in (None, ""):
                continue
            if not isinstance(raw, str) or not 8 <= len(raw) <= 128:
                issues.append(_issue(name, "Use 8 to 128 characters."))
                continue
            values[password_column] = await hash_password_async(raw)
            continue
        spec = fields.get(name)
        if spec is None:
            issues.append(_issue(name, "Unknown field.", "extra_forbidden"))
            continue
        # Composite keys (link tables) are entered on create and can be changed later.
        if spec.readonly or (spec.primary_key and admin.auto_pk):
            continue  # read-only fields are ignored, as in a Django form
        blank = isinstance(raw, str) and not raw.strip()
        if blank and spec.required and spec.kind in ("string", "text"):
            issues.append(_issue(name, "This field is required.", "missing"))
            continue
        if raw is None or (blank and spec.kind not in ("string", "text")):
            if spec.nullable:
                values[name] = None
            else:
                issues.append(_issue(name, "This field is required.", "missing"))
            continue
        try:
            values[name] = _coerce(spec, raw)
        except ValueError as exc:
            issues.append(_issue(name, str(exc)))
    if creating:
        for spec in admin.fields:
            if spec.required and spec.name not in values and not any(i["loc"][1] == spec.name for i in issues):
                issues.append(_issue(spec.name, "This field is required.", "missing"))
        if password_column and password_column not in values and "password" not in payload:
            issues.append(_issue("password", "This field is required.", "missing"))
    if issues:
        raise ValidationFailed("Please correct the errors below.", details=issues)
    return values


def _insert_values(admin: AdminModel, values: dict[str, Any]) -> dict[str, Any]:
    """Apply the model's Python defaults (ids, timestamps, JSON factories) to an insert."""
    instance = admin.model(**{admin.table.c[name].key: value for name, value in values.items()})
    out: dict[str, Any] = {}
    for column in admin.table.columns:
        value = getattr(instance, column.key, None)
        if column.name in values or value is not None or column.server_default is None:
            out[column.name] = values.get(column.name, value)
    return out


# -- database errors --------------------------------------------------------------------

_KEY_COLUMNS = re.compile(r"Key \((?P<cols>[^)]+)\)")


def _translate(admin: AdminModel, exc: DBAPIError) -> Exception:
    orig = exc.orig
    cause = getattr(orig, "__cause__", None) or orig
    sqlstate = getattr(cause, "sqlstate", None) or getattr(orig, "sqlstate", None)
    message = getattr(cause, "message", None) or str(cause)
    detail = getattr(cause, "detail", None)
    column = getattr(cause, "column_name", None)
    constraint = getattr(cause, "constraint_name", None)
    if not column and detail and (match := _KEY_COLUMNS.search(detail)):
        column = match.group("cols").split(",")[0].strip()
    info = {"constraint": constraint, "detail": detail, "sqlstate": sqlstate}
    if sqlstate == "23505" and column:  # unique_violation
        return ValidationFailed(
            "A record with this value already exists.",
            details=[_issue(column, "A record with this value already exists.", "unique")],
        )
    if sqlstate == "23502" and column:  # not_null_violation
        return ValidationFailed(
            "This field is required.", details=[_issue(column, "This field is required.", "missing")]
        )
    if sqlstate == "23503":  # foreign_key_violation
        if detail and "is still referenced" in detail:
            return Conflict(
                "This record is still referenced by other records (protected relation).",
                code="protected_relation",
                details=info,
            )
        if column:
            return ValidationFailed(
                "The selected record does not exist.",
                details=[_issue(column, "The selected record does not exist.", "foreign_key")],
            )
    if sqlstate == "23001":  # restrict_violation: immutability triggers
        return Conflict(message, code="immutable_record", details=info)
    if sqlstate == "23514":  # check_violation
        return ValidationFailed(
            f"Check constraint failed: {constraint or message}.", code="check_violation", details=info
        )
    if sqlstate and sqlstate.startswith("22"):  # data exceptions (out of range, invalid text…)
        return ValidationFailed(message, code="invalid_data", details=info)
    return Conflict(message, code="integrity_error", details=info)


async def _conn(db: AsyncSession) -> AsyncConnection:
    return await db.connection()


async def _run(db: AsyncSession, admin: AdminModel, stmt: Any, *, override: bool = False) -> Any:
    """Execute a write in a savepoint, translating database errors.

    ``override`` lifts an append-only table's immutability trigger for this statement only:
    ``ALTER TABLE … DISABLE TRIGGER`` is transactional and holds an exclusive lock until the
    request commits, so no other session ever sees the table unprotected, and the trigger is
    re-enabled before the savepoint is released (or rolled back with it on error).
    """
    conn = await _conn(db)
    trigger = admin.config.immutable_trigger if override else None
    try:
        async with conn.begin_nested():
            if trigger:
                await conn.execute(text(f'ALTER TABLE "{admin.table.name}" DISABLE TRIGGER "{trigger}"'))
            result = await conn.execute(stmt)
            if trigger:
                await conn.execute(text(f'ALTER TABLE "{admin.table.name}" ENABLE TRIGGER "{trigger}"'))
            return result
    except (IntegrityError, DBAPIError) as exc:
        raise _translate(admin, exc) from exc


async def check_balanced(db: AsyncSession, admin: AdminModel, group_ids: Iterable[Any]) -> None:
    """Every affected ledger transaction must still balance (sum of debits = sum of credits)."""
    column_name = admin.config.balanced_by
    ids = {i for i in group_ids if i is not None}
    if not column_name or not ids:
        return
    t = admin.table
    debit = func.coalesce(func.sum(t.c.amount).filter(t.c.direction == "DEBIT"), 0)
    credit = func.coalesce(func.sum(t.c.amount).filter(t.c.direction == "CREDIT"), 0)
    group = t.c[column_name]
    stmt = select(group, debit - credit).where(group.in_(ids)).group_by(group).having(debit != credit)
    conn = await _conn(db)
    unbalanced = (await conn.execute(stmt)).all()
    if unbalanced:
        raise ValidationFailed(
            "Ledger transactions must balance: total debits must equal total credits.",
            code="ledger_unbalanced",
            details=[{"transaction_id": str(g), "imbalance": int(d)} for g, d in unbalanced],
        )


async def invalidate_caches(admin: AdminModel) -> None:
    if admin.config.cache_keys:
        await cache_delete(*admin.config.cache_keys)


# -- reading ----------------------------------------------------------------------------


def _ordering(admin: AdminModel, ordering: str | None) -> list[Any]:
    names = admin.by_name
    requested = [o.strip() for o in (ordering or "").split(",") if o.strip()]
    valid = [o for o in requested if o.lstrip("-") in names]
    clauses: list[Any] = []
    for item in valid or list(admin.ordering):
        column = admin.table.c[item.lstrip("-")]
        clauses.append(desc(column).nulls_last() if item.startswith("-") else asc(column).nulls_first())
    # A stable tiebreaker keeps pagination deterministic.
    clauses.extend(asc(admin.table.c[name]) for name in admin.pk)
    return clauses


def _search_clause(admin: AdminModel, q: str) -> ColumnElement[bool] | None:
    q = q.strip()
    if not q:
        return None
    terms: list[ColumnElement[bool]] = []
    for word in q.split():
        pattern = f"%{word.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')}%"
        per_word: list[ColumnElement[bool]] = [admin.table.c[n].ilike(pattern) for n in admin.search_fields]
        try:
            as_uuid = uuid.UUID(word)
        except ValueError:
            as_uuid = None
        if as_uuid is not None:
            per_word.extend(admin.table.c[f.name] == as_uuid for f in admin.fields if f.kind == "uuid")
        if not per_word:
            return false()
        terms.append(or_(*per_word))
    return and_(*terms)


def filter_clauses(admin: AdminModel, params: Iterable[tuple[str, str]]) -> list[ColumnElement[bool]]:
    """Django-style lookups from the query string: ``field``, ``field__gte``, ``field__isnull``…"""
    clauses: list[ColumnElement[bool]] = []
    issues: list[dict[str, Any]] = []
    fields = admin.by_name
    for key, raw in params:
        name, _, lookup = key.partition("__")
        lookup = lookup or "exact"
        spec = fields.get(name)
        if spec is None or lookup not in LOOKUPS:
            continue
        column = admin.table.c[name]
        try:
            if lookup == "isnull":
                null = _coerce(_bool_spec(spec), raw)
                clauses.append(column.is_(None) if null else column.is_not(None))
            elif lookup == "icontains":
                clauses.append(cast(column, String).ilike(f"%{raw}%"))
            elif lookup == "in":
                clauses.append(column.in_([_lookup_value(spec, part) for part in raw.split(",") if part]))
            elif raw == "" and spec.nullable and lookup == "exact":
                clauses.append(column.is_(None))
            else:
                value = _lookup_value(spec, raw)
                op = {"exact": column.__eq__, "gte": column.__ge__, "lte": column.__le__}
                op |= {"gt": column.__gt__, "lt": column.__lt__}
                clauses.append(op[lookup](value))
        except ValueError as exc:
            issues.append({"loc": ["query", key], "msg": str(exc), "type": "value_error"})
    if issues:
        raise ValidationFailed("Invalid filter.", details=issues)
    return clauses


def _bool_spec(spec: FieldSpec) -> FieldSpec:
    return FieldSpec(
        name=spec.name,
        kind="boolean",
        nullable=False,
        primary_key=False,
        required=False,
        readonly=False,
        max_length=None,
        choices=None,
        fk=None,
        on_delete=None,
        column=spec.column,
    )


def _lookup_value(spec: FieldSpec, raw: str) -> Any:
    if spec.kind in ("string", "text"):
        return raw  # filters never reject a string (choices included)
    if spec.kind == "json":
        raise ValueError("JSON fields cannot be filtered this way.")
    return _coerce(spec, raw)


async def list_rows(
    db: AsyncSession,
    admin: AdminModel,
    *,
    q: str | None,
    filters: list[ColumnElement[bool]],
    ordering: str | None,
    page: int,
    page_size: int,
) -> tuple[list[RowMapping], int]:
    stmt: Select[Any] = select(admin.table)
    conditions = list(filters)
    if q and (search := _search_clause(admin, q)) is not None:
        conditions.append(search)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    conn = await _conn(db)
    total = (await conn.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        (await conn.execute(stmt.order_by(*_ordering(admin, ordering)).limit(page_size).offset((page - 1) * page_size)))
        .mappings()
        .all()
    )
    return list(rows), int(total)


async def get_row(db: AsyncSession, admin: AdminModel, raw_pk: str) -> RowMapping:
    conn = await _conn(db)
    row = (await conn.execute(select(admin.table).where(pk_clause(admin, parse_pk(admin, raw_pk))))).mappings().first()
    if row is None:
        raise NotFound("Record not found.")
    return row


# -- labels (the admin's ``__str__``) -------------------------------------------------------


def _short(value: Any) -> str:
    text = str(value)
    return text[:8] if isinstance(value, uuid.UUID) else text


async def labels(db: AsyncSession, admin: AdminModel, rows: Sequence[RowMapping], depth: int = 1) -> list[str]:
    """A readable label per row from its display columns; foreign keys resolve one level deep."""
    resolved: dict[str, dict[Any, str]] = {}
    if depth > 0:
        for name in admin.display:
            spec = admin.by_name[name]
            if spec.fk:
                resolved[name] = await fk_labels(db, spec.fk, {r[name] for r in rows if r[name] is not None}, depth - 1)
    out: list[str] = []
    for row in rows:
        parts: list[str] = []
        for name in admin.display:
            value = row[name]
            if value is None:
                continue
            parts.append(resolved.get(name, {}).get(value) or _short(value))
        out.append(" · ".join(parts) or f"{admin.key} {_short(row[admin.pk[0]])}")
    return out


async def fk_labels(db: AsyncSession, target_key: str, ids: set[Any], depth: int = 0) -> dict[Any, str]:
    target = get_model(target_key)
    if target is None or not ids or len(target.pk) != 1:
        return {}
    pk_col = target.table.c[target.pk[0]]
    conn = await _conn(db)
    rows = (await conn.execute(select(target.table).where(pk_col.in_(ids)))).mappings().all()
    names = await labels(db, target, rows, depth)
    return {row[target.pk[0]]: name for row, name in zip(rows, names, strict=True)}


async def list_fk_labels(
    db: AsyncSession, admin: AdminModel, rows: Sequence[RowMapping], columns: Iterable[str]
) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for name in columns:
        spec = admin.by_name[name]
        if spec.fk:
            found = await fk_labels(db, spec.fk, {r[name] for r in rows if r[name] is not None})
            out[name] = {str(k): v for k, v in found.items()}
    return out


async def lookup(
    db: AsyncSession, admin: AdminModel, *, q: str | None, pks: Sequence[str], limit: int = LOOKUP_LIMIT
) -> list[tuple[str, str]]:
    stmt: Select[Any] = select(admin.table)
    if pks:
        stmt = stmt.where(pks_clause(admin, pks))
    elif q and (search := _search_clause(admin, q)) is not None:
        stmt = stmt.where(search)
    conn = await _conn(db)
    rows = (await conn.execute(stmt.order_by(*_ordering(admin, None)).limit(limit))).mappings().all()
    names = await labels(db, admin, rows)
    return [(pk_string(admin, row), name) for row, name in zip(rows, names, strict=True)]


# -- relations --------------------------------------------------------------------------


async def related_counts(db: AsyncSession, admin: AdminModel, raw_pks: Sequence[str]) -> list[dict[str, Any]]:
    """Rows in other tables that reference the given records (Django's "related objects")."""
    if len(admin.pk) != 1 or not raw_pks:
        return []
    ids = [parse_pk(admin, r)[0] for r in raw_pks]
    conn = await _conn(db)
    out: list[dict[str, Any]] = []
    for rel in admin.reverse_relations():
        source = registry()[rel.model]
        column = source.table.c[rel.field]
        count = (await conn.execute(select(func.count()).where(column.in_(ids)))).scalar_one()
        if count:
            out.append({"model": rel.model, "field": rel.field, "on_delete": rel.on_delete, "count": int(count)})
    return out


async def delete_preview(db: AsyncSession, admin: AdminModel, raw_pks: Sequence[str]) -> dict[str, Any]:
    """What a delete would do: cascades (recursively), unlinks, and protected references."""
    deleted: dict[str, int] = {}
    unlinked: dict[tuple[str, str], int] = {}
    protected: dict[tuple[str, str], int] = {}
    conn = await _conn(db)

    async def walk(model: AdminModel, where: ColumnElement[bool], depth: int) -> None:
        if len(model.pk) != 1 or depth > 6:
            return
        ids = select(model.table.c[model.pk[0]]).where(where).scalar_subquery()
        for rel in model.reverse_relations():
            source = registry()[rel.model]
            column = source.table.c[rel.field]
            condition = column.in_(ids)
            count = int((await conn.execute(select(func.count()).where(condition))).scalar_one())
            if not count:
                continue
            if APPEND_ONLY in source.config.notes:
                # Cascading into (or nulling a column of) an append-only table is rejected by
                # its immutability trigger, so the reference protects the record.
                protected[(rel.model, rel.field)] = protected.get((rel.model, rel.field), 0) + count
            elif rel.on_delete == "CASCADE":
                deleted[rel.model] = deleted.get(rel.model, 0) + count
                await walk(source, condition, depth + 1)
            elif rel.on_delete == "SET NULL":
                unlinked[(rel.model, rel.field)] = unlinked.get((rel.model, rel.field), 0) + count
            else:
                protected[(rel.model, rel.field)] = protected.get((rel.model, rel.field), 0) + count

    rows = (await conn.execute(select(admin.table).where(pks_clause(admin, raw_pks)))).mappings().all()
    if len(rows) != len(set(raw_pks)):
        raise NotFound("Record not found.")
    await walk(admin, pks_clause(admin, raw_pks), 0)
    return {
        "objects": [
            {"pk": pk_string(admin, row), "label": name}
            for row, name in zip(rows, await labels(db, admin, rows), strict=True)
        ],
        "cascades": [{"model": k, "count": v} for k, v in sorted(deleted.items())],
        "unlinks": [{"model": m, "field": f, "count": c} for (m, f), c in sorted(unlinked.items())],
        "protected": [{"model": m, "field": f, "count": c} for (m, f), c in sorted(protected.items())],
    }


# -- writing ----------------------------------------------------------------------------


async def create_row(db: AsyncSession, admin: AdminModel, values: dict[str, Any]) -> RowMapping:
    for name in admin.config.generated:
        # A random, never-disclosed token: the row exists but can never be redeemed.
        values.setdefault(name, hash_token(generate_token()))
    stmt = insert(admin.table).values(**_insert_values(admin, values)).returning(*admin.table.columns)
    row: RowMapping = (await _run(db, admin, stmt)).mappings().one()
    return row


async def update_row(
    db: AsyncSession, admin: AdminModel, raw_pk: str, values: dict[str, Any], *, override: bool = False
) -> tuple[RowMapping, RowMapping]:
    before = await get_row(db, admin, raw_pk)
    if not values:
        return before, before
    stmt = (
        update(admin.table)
        .where(pk_clause(admin, parse_pk(admin, raw_pk)))
        .values(**values)
        .returning(*admin.table.columns)
    )
    after = (await _run(db, admin, stmt, override=override)).mappings().one()
    return before, after


async def delete_rows(
    db: AsyncSession, admin: AdminModel, raw_pks: Sequence[str], *, override: bool = False
) -> list[RowMapping]:
    conn = await _conn(db)
    rows = (await conn.execute(select(admin.table).where(pks_clause(admin, raw_pks)))).mappings().all()
    if len(rows) != len(set(raw_pks)):
        raise NotFound("Record not found.")
    await _run(db, admin, delete(admin.table).where(pks_clause(admin, raw_pks)), override=override)
    return list(rows)


# -- inlines (child rows edited on the parent's page) -------------------------------------


def _prefix_issues(exc: ValidationFailed, prefix: list[Any]) -> ValidationFailed:
    details = []
    for issue in exc.details or []:
        loc = list(issue.get("loc", []))
        details.append({**issue, "loc": ["body", *prefix, *loc[1:]]})
    return ValidationFailed(exc.message, code=exc.code, details=details)


class InlineChange:
    """One child row written through an inline, for the audit log."""

    def __init__(self, admin: AdminModel, action: str, pk: str, before: Any, after: Any) -> None:
        self.admin, self.action, self.pk, self.before, self.after = admin, action, pk, before, after


async def apply_inlines(
    db: AsyncSession,
    parent: AdminModel,
    parent_row: RowMapping,
    payload: Any,
    *,
    authorize_override: Any,
) -> list[InlineChange]:
    """Create, change and delete child rows: ``{"<child table>": [{...}, {"_pk": …}, {"_pk": …, "_delete": true}]}``.

    ``authorize_override(child)`` is called before any change to an append-only child and
    must raise if the caller may not override it.
    """
    if payload in (None, {}):
        return []
    if not isinstance(payload, dict):
        raise ValidationFailed("Invalid inlines.", details=[_issue("_inlines", "Expected an object.")])
    allowed = dict(parent.config.inlines)
    parent_pk = parent_row[parent.pk[0]]
    changes: list[InlineChange] = []
    balance: dict[str, set[Any]] = {}
    for child_key, items in payload.items():
        if child_key not in allowed or not isinstance(items, list):
            raise ValidationFailed("Invalid inlines.", details=[_issue("_inlines", f"Unknown inline {child_key!r}.")])
        child = registry()[child_key]
        fk = allowed[child_key]
        for index, item in enumerate(items):
            prefix = ["_inlines", child_key, index]
            if not isinstance(item, dict):
                raise ValidationFailed(
                    "Invalid inline row.",
                    details=[{"loc": ["body", *prefix], "msg": "Expected an object.", "type": "type_error"}],
                )
            data = {k: v for k, v in item.items() if k not in ("_pk", "_delete")}
            data.pop(fk, None)  # always the parent
            raw_pk = item.get("_pk")
            try:
                if raw_pk is None:
                    require(child, "add")
                    values = await parse_payload(child, {**data, fk: str(parent_pk)}, creating=True)
                    row = await create_row(db, child, values)
                    changes.append(
                        InlineChange(child, "data.create", pk_string(child, row), None, snapshot(child, row))
                    )
                    if child.config.balanced_by:
                        balance.setdefault(child_key, set()).add(row[child.config.balanced_by])
                    continue
                existing = await get_row(db, child, str(raw_pk))
                if existing[fk] != parent_pk:
                    raise NotFound("Record not found.")
                if child.immutable:
                    authorize_override(child)
                if item.get("_delete") is True:
                    require(child, "delete")
                    await delete_rows(db, child, [str(raw_pk)], override=child.immutable)
                    changes.append(InlineChange(child, "data.delete", str(raw_pk), snapshot(child, existing), None))
                else:
                    require(child, "change")
                    values = await parse_payload(child, data, creating=False)
                    before, after = await update_row(db, child, str(raw_pk), values, override=child.immutable)
                    old, new = changed(before, after, child)
                    if old or new:
                        changes.append(InlineChange(child, "data.update", pk_string(child, after), old, new))
                if child.config.balanced_by:
                    balance.setdefault(child_key, set()).add(existing[child.config.balanced_by])
            except ValidationFailed as exc:
                raise _prefix_issues(exc, prefix) from exc
    for child_key, ids in balance.items():
        await check_balanced(db, registry()[child_key], ids)
    return changes


def snapshot(admin: AdminModel, row: RowMapping) -> dict[str, Any]:
    """Audit snapshot of a row (hidden columns such as password hashes are left out)."""
    return row_values(admin, row)


def changed(before: RowMapping, after: RowMapping, admin: AdminModel) -> tuple[dict[str, Any], dict[str, Any]]:
    keys = [f.name for f in admin.fields if serialize(before[f.name]) != serialize(after[f.name])]
    return {k: serialize(before[k]) for k in keys}, {k: serialize(after[k]) for k in keys}
