"""/api/v1/admin/data/* — generic CRUD for every table (a Django-admin-style data admin).

* Browsing needs ``admin.data.view``; creating, changing and deleting need
  ``admin.data.manage`` (SUPER_ADMIN by default).
* Append-only tables (ledger, audit log, verification and delivery timelines) accept new
  rows like any other table. Changing or deleting their rows additionally needs
  ``admin.data.override_immutable`` and a reason in the ``X-Override-Reason`` header; the
  table's immutability trigger is lifted for that one statement only.
* Every write is recorded in the audit log (``data.create`` / ``data.update`` /
  ``data.delete``, or ``data.override.*`` with the reason) with before/after snapshots.
* Database rules still apply: ``ON DELETE RESTRICT`` relations, check constraints, unique
  indexes and the ledger balance reject the change with a clear error.
"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Query, Request, status
from pydantic import BaseModel, Field

from app.api.deps import AuthContext, client_ip, require_permission
from app.core.errors import PermissionDenied, ValidationFailed
from app.database.session import DbSession
from app.modules.admin.audit import record_audit
from app.modules.admin.data import service
from app.modules.admin.data.registry import AdminModel, FieldKind, registry
from app.modules.auth.permissions import Perm
from app.modules.auth.service import revoke_all_sessions

router = APIRouter(prefix="/admin/data", tags=["admin-data"])

DataViewAuth = Annotated[AuthContext, Depends(require_permission(Perm.DATA_VIEW))]
DataManageAuth = Annotated[AuthContext, Depends(require_permission(Perm.DATA_VIEW, Perm.DATA_MANAGE))]
OverrideReason = Annotated[str | None, Header(alias="x-override-reason", max_length=500)]

RESERVED_PARAMS = frozenset({"page", "page_size", "q", "ordering"})
INLINES_KEY = "_inlines"
MIN_REASON = 5


# -- schemas ----------------------------------------------------------------------------


class ModelSummary(BaseModel):
    key: str
    group: str
    can_add: bool
    can_change: bool
    can_delete: bool
    # Append-only table: changes and deletes are overrides (permission + reason).
    immutable: bool
    # Whether the current user may write (``admin.data.manage``) and override append-only
    # rows (``admin.data.override_immutable``); the flags above are what the model allows.
    user_can_manage: bool
    user_can_override: bool
    # New rows are added through this parent's inline (e.g. ledger entries).
    add_via: str | None
    notes: list[str]


class FieldOut(BaseModel):
    name: str
    kind: FieldKind | Literal["password"]
    nullable: bool
    primary_key: bool
    required: bool
    readonly: bool
    max_length: int | None
    choices: list[str] | None
    fk: str | None
    on_delete: str | None


class RelationOut(BaseModel):
    model: str
    field: str
    on_delete: str


class InlineOut(BaseModel):
    model: str
    fk: str


class ModelSchema(ModelSummary):
    pk: list[str]
    auto_pk: bool
    display: list[str]
    fields: list[FieldOut]
    list_display: list[str]
    search_fields: list[str]
    list_filter: list[str]
    ordering: list[str]
    relations: list[RelationOut]
    inlines: list[InlineOut]


class RowOut(BaseModel):
    pk: str
    label: str
    values: dict[str, Any]


class RowPage(BaseModel):
    items: list[RowOut]
    total: int
    page: int
    page_size: int
    # Labels of the referenced records for foreign-key columns: {column: {id: label}}.
    fk_labels: dict[str, dict[str, str]]


class RelatedCount(BaseModel):
    model: str
    field: str
    on_delete: str
    count: int


class RowDetail(RowOut):
    fk_labels: dict[str, dict[str, str]]
    related: list[RelatedCount]


class LookupItem(BaseModel):
    pk: str
    label: str


class PkList(BaseModel):
    pks: list[str] = Field(min_length=1, max_length=500)


class DeleteObject(BaseModel):
    pk: str
    label: str


class CascadeCount(BaseModel):
    model: str
    count: int


class FieldCount(BaseModel):
    model: str
    field: str
    count: int


class DeletePreview(BaseModel):
    objects: list[DeleteObject]
    cascades: list[CascadeCount]
    unlinks: list[FieldCount]
    protected: list[FieldCount]


class DeleteResult(BaseModel):
    deleted: int


# -- helpers ----------------------------------------------------------------------------


def _summary(admin: AdminModel, ctx: AuthContext) -> dict[str, Any]:
    codes = ctx.user.permission_codes
    return {
        "key": admin.key,
        "group": admin.group,
        "can_add": admin.can_add,
        "can_change": admin.can_change,
        "can_delete": admin.can_delete,
        "immutable": admin.immutable,
        "user_can_manage": Perm.DATA_MANAGE.value in codes,
        "user_can_override": Perm.DATA_MANAGE.value in codes and Perm.DATA_OVERRIDE_IMMUTABLE.value in codes,
        "add_via": admin.config.add_via,
        "notes": list(admin.config.notes),
    }


def _schema(admin: AdminModel, ctx: AuthContext) -> ModelSchema:
    fields = [
        FieldOut(
            name=f.name,
            kind=f.kind,
            nullable=f.nullable,
            primary_key=f.primary_key,
            required=f.required,
            readonly=f.readonly,
            max_length=f.max_length,
            choices=list(f.choices) if f.choices else None,
            fk=f.fk,
            on_delete=f.on_delete,
        )
        for f in admin.fields
    ]
    if admin.config.password_column:
        fields.append(
            FieldOut(
                name="password",
                kind="password",
                nullable=True,
                primary_key=False,
                required=True,
                readonly=False,
                max_length=128,
                choices=None,
                fk=None,
                on_delete=None,
            )
        )
    return ModelSchema(
        **_summary(admin, ctx),
        pk=list(admin.pk),
        auto_pk=admin.auto_pk,
        display=list(admin.display),
        fields=fields,
        list_display=list(admin.list_display),
        search_fields=list(admin.search_fields),
        list_filter=list(admin.list_filter),
        ordering=list(admin.ordering),
        relations=[RelationOut(model=r.model, field=r.field, on_delete=r.on_delete) for r in admin.reverse_relations()],
        inlines=[InlineOut(model=m, fk=fk) for m, fk in admin.config.inlines],
    )


async def _detail(db: DbSession, admin: AdminModel, row: Any) -> RowDetail:
    pk = service.pk_string(admin, row)
    fk_columns = [f.name for f in admin.fields if f.fk]
    return RowDetail(
        pk=pk,
        label=(await service.labels(db, admin, [row]))[0],
        values=service.row_values(admin, row),
        fk_labels=await service.list_fk_labels(db, admin, [row], fk_columns),
        related=[RelatedCount(**r) for r in await service.related_counts(db, admin, [pk])],
    )


def _guard_self(ctx: AuthContext, admin: AdminModel, pks: list[str]) -> None:
    if admin.key == "users" and str(ctx.user_id) in pks:
        raise PermissionDenied("You cannot delete your own account.", code="cannot_delete_self")


class _Override:
    """Authorises overrides of append-only rows for one request."""

    def __init__(self, ctx: AuthContext, reason: str | None) -> None:
        self.ctx = ctx
        self.reason = (reason or "").strip()

    def __call__(self, admin: AdminModel) -> None:
        if Perm.DATA_OVERRIDE_IMMUTABLE.value not in self.ctx.user.permission_codes:
            raise PermissionDenied(
                f"Records in {admin.key} are append-only; changing them requires "
                f"the {Perm.DATA_OVERRIDE_IMMUTABLE.value} permission.",
                code="override_permission_required",
                details=[Perm.DATA_OVERRIDE_IMMUTABLE.value],
            )
        if len(self.reason) < MIN_REASON:
            raise ValidationFailed(
                "Give a reason for changing an append-only record.",
                code="override_reason_required",
                details=[{"loc": ["header", "x-override-reason"], "msg": "Enter a reason.", "type": "missing"}],
            )

    def action(self, admin: AdminModel, verb: str) -> str:
        return f"data.override.{verb}" if admin.immutable else f"data.{verb}"

    def tag(self, admin: AdminModel, snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
        """Add the override reason to an audit snapshot."""
        if not admin.immutable:
            return snapshot
        return {**(snapshot or {}), "_override_reason": self.reason}


def _split_inlines(payload: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    body = dict(payload)
    return body, body.pop(INLINES_KEY, None)


async def _audit_inlines(
    db: DbSession, request: Request, ctx: AuthContext, override: _Override, changes: list[service.InlineChange]
) -> None:
    for change in changes:
        verb = change.action.removeprefix("data.")
        overridden = change.admin.immutable and verb != "create"
        await record_audit(
            db,
            actor_user_id=ctx.user_id,
            action=f"data.override.{verb}" if overridden else change.action,
            entity_type=change.admin.key,
            entity_id=change.pk,
            before=change.before,
            after=override.tag(change.admin, change.after) if overridden else change.after,
            ip_address=client_ip(request),
        )


# -- endpoints --------------------------------------------------------------------------


@router.get("/models")
async def list_models(ctx: DataViewAuth) -> list[ModelSummary]:
    return [ModelSummary(**_summary(m, ctx)) for m in registry().values()]


@router.get("/models/{model}")
async def model_schema(model: str, ctx: DataViewAuth) -> ModelSchema:
    return _schema(service.resolve(model), ctx)


@router.get("/{model}")
async def list_rows(
    model: str,
    request: Request,
    ctx: DataViewAuth,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
    q: Annotated[str | None, Query(max_length=200)] = None,
    ordering: Annotated[str | None, Query(max_length=200)] = None,
) -> RowPage:
    """List records. Filter with Django-style lookups in the query string, e.g.
    ``?status=PAID&total__gte=1000&paid_at__isnull=false&merchant_id=<uuid>``."""
    admin = service.resolve(model)
    filters = service.filter_clauses(
        admin, [(k, v) for k, v in request.query_params.multi_items() if k not in RESERVED_PARAMS]
    )
    rows, total = await service.list_rows(
        db, admin, q=q, filters=filters, ordering=ordering, page=page, page_size=page_size
    )
    labels = await service.labels(db, admin, rows)
    return RowPage(
        items=[
            RowOut(pk=service.pk_string(admin, r), label=label, values=service.row_values(admin, r))
            for r, label in zip(rows, labels, strict=True)
        ],
        total=total,
        page=page,
        page_size=page_size,
        fk_labels=await service.list_fk_labels(db, admin, rows, admin.list_display),
    )


@router.get("/{model}/lookup")
async def lookup(
    model: str,
    ctx: DataViewAuth,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=200)] = None,
    pk: Annotated[list[str] | None, Query(max_length=100)] = None,
) -> list[LookupItem]:
    """Search records by their search fields (or fetch labels for ``pk``), for pickers."""
    admin = service.resolve(model)
    return [LookupItem(pk=p, label=label) for p, label in await service.lookup(db, admin, q=q, pks=pk or [])]


@router.post("/{model}", status_code=status.HTTP_201_CREATED)
async def create_row(
    model: str,
    payload: dict[str, Any],
    request: Request,
    ctx: DataManageAuth,
    db: DbSession,
    x_override_reason: OverrideReason = None,
) -> RowDetail:
    """Create a record. Inline child rows (e.g. a ledger transaction's entries) go in
    ``_inlines``: ``{"_inlines": {"ledger_entries": [{...}, {...}]}}``."""
    admin = service.resolve(model)
    service.require(admin, "add")
    override = _Override(ctx, x_override_reason)
    body, inlines = _split_inlines(payload)
    values = await service.parse_payload(admin, body, creating=True)
    row = await service.create_row(db, admin, values)
    changes = await service.apply_inlines(db, admin, row, inlines, authorize_override=override)
    if admin.config.balanced_by:
        await service.check_balanced(db, admin, [row[admin.config.balanced_by]])
    await record_audit(
        db,
        actor_user_id=ctx.user_id,
        action="data.create",
        entity_type=admin.key,
        entity_id=service.pk_string(admin, row),
        after=service.snapshot(admin, row),
        ip_address=client_ip(request),
    )
    await _audit_inlines(db, request, ctx, override, changes)
    await service.invalidate_caches(admin)
    return await _detail(db, admin, row)


@router.post("/{model}/delete-preview")
async def delete_preview(model: str, body: PkList, ctx: DataManageAuth, db: DbSession) -> DeletePreview:
    """What deleting these records would also delete, unlink, or be blocked by."""
    admin = service.resolve(model)
    service.require(admin, "delete")
    return DeletePreview.model_validate(await service.delete_preview(db, admin, body.pks))


@router.post("/{model}/bulk-delete")
async def bulk_delete(
    model: str,
    body: PkList,
    request: Request,
    ctx: DataManageAuth,
    db: DbSession,
    x_override_reason: OverrideReason = None,
) -> DeleteResult:
    """Delete several records in one transaction (all or nothing)."""
    admin = service.resolve(model)
    service.require(admin, "delete")
    _guard_self(ctx, admin, body.pks)
    override = _Override(ctx, x_override_reason)
    if admin.immutable:
        override(admin)
    rows = await service.delete_rows(db, admin, body.pks, override=admin.immutable)
    if admin.config.balanced_by:
        await service.check_balanced(db, admin, [r[admin.config.balanced_by] for r in rows])
    for row in rows:
        await record_audit(
            db,
            actor_user_id=ctx.user_id,
            action=override.action(admin, "delete"),
            entity_type=admin.key,
            entity_id=service.pk_string(admin, row),
            before=service.snapshot(admin, row),
            after=override.tag(admin, None),
            ip_address=client_ip(request),
        )
    await service.invalidate_caches(admin)
    return DeleteResult(deleted=len(rows))


@router.get("/{model}/{pk}")
async def get_row(model: str, pk: str, ctx: DataViewAuth, db: DbSession) -> RowDetail:
    admin = service.resolve(model)
    return await _detail(db, admin, await service.get_row(db, admin, pk))


@router.patch("/{model}/{pk}")
async def update_row(
    model: str,
    pk: str,
    payload: dict[str, Any],
    request: Request,
    ctx: DataManageAuth,
    db: DbSession,
    x_override_reason: OverrideReason = None,
) -> RowDetail:
    """Change a record (only the fields sent). Inline child rows go in ``_inlines``: new
    rows without ``_pk``, changed rows with ``_pk``, removed rows with ``_pk`` and ``_delete``."""
    admin = service.resolve(model)
    override = _Override(ctx, x_override_reason)
    body, inlines = _split_inlines(payload)
    values = await service.parse_payload(admin, body, creating=False)
    if values or not inlines:
        service.require(admin, "change")
    if values and admin.immutable:
        override(admin)
    before, after = await service.update_row(db, admin, pk, values, override=admin.immutable)
    changes = await service.apply_inlines(db, admin, after, inlines, authorize_override=override)
    if admin.config.balanced_by:
        await service.check_balanced(db, admin, [before[admin.config.balanced_by], after[admin.config.balanced_by]])
    old, new = service.changed(before, after, admin)
    password_changed = bool(admin.config.password_column and admin.config.password_column in values)
    if password_changed:
        new["password"] = "(changed)"  # noqa: S105 (audit marker, never the value)
        await revoke_all_sessions(db, after["id"], reason="password_set_by_admin")
    if old or new:
        await record_audit(
            db,
            actor_user_id=ctx.user_id,
            action=override.action(admin, "update"),
            entity_type=admin.key,
            entity_id=service.pk_string(admin, after),
            before=old,
            after=override.tag(admin, new),
            ip_address=client_ip(request),
        )
    await _audit_inlines(db, request, ctx, override, changes)
    await service.invalidate_caches(admin)
    return await _detail(db, admin, after)


@router.delete("/{model}/{pk}")
async def delete_row(
    model: str,
    pk: str,
    request: Request,
    ctx: DataManageAuth,
    db: DbSession,
    x_override_reason: OverrideReason = None,
) -> DeleteResult:
    admin = service.resolve(model)
    service.require(admin, "delete")
    _guard_self(ctx, admin, [pk])
    override = _Override(ctx, x_override_reason)
    if admin.immutable:
        override(admin)
    rows = await service.delete_rows(db, admin, [pk], override=admin.immutable)
    if admin.config.balanced_by:
        await service.check_balanced(db, admin, [rows[0][admin.config.balanced_by]])
    await record_audit(
        db,
        actor_user_id=ctx.user_id,
        action=override.action(admin, "delete"),
        entity_type=admin.key,
        entity_id=pk,
        before=service.snapshot(admin, rows[0]),
        after=override.tag(admin, None),
        ip_address=client_ip(request),
    )
    await service.invalidate_caches(admin)
    return DeleteResult(deleted=1)
