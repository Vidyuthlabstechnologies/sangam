from sqlalchemy import event, inspect as sa_inspect
from sqlalchemy.orm import declarative_base

Base = declarative_base()


@event.listens_for(Base, "init", propagate=True)
def _apply_scalar_defaults(target, args, kwargs):
    """Apply scalar column defaults at construction time, not only at INSERT.

    SQLAlchemy's ``default=`` fires when a row is inserted. Until then the
    attribute is ``None``, so code reading state off a freshly-constructed
    object silently sees ``None`` instead of the declared default::

        wf = Workflow(name="x", initiator_id=...)
        wf.state == WorkflowState.DRAFT   # False — it is None

    That is a footgun for validation and branching that runs before commit.
    This listener fills in scalar defaults (enums, booleans, numbers, strings)
    up front so objects are consistent from the moment they exist.

    Callable defaults (``uuid.uuid4``, ``datetime.utcnow``, ``list``) are
    deliberately left to INSERT time: generating identifiers and timestamps
    at construction would change their meaning, and mutable defaults must not
    be shared between instances.
    """
    mapper = sa_inspect(type(target), raiseerr=False)
    if mapper is None:
        return

    for attr in mapper.column_attrs:
        if attr.key in kwargs:
            continue
        column = attr.columns[0]
        default = column.default
        if default is not None and default.is_scalar:
            kwargs[attr.key] = default.arg
