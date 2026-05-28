from logging.config import fileConfig

from alembic import context

from db import engine
from modelos import Base

# Objeto de configuração do Alembic (acessa o alembic.ini).
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadados dos nossos modelos — base do autogenerate.
target_metadata = Base.metadata


def include_name(name, type_, parent_names):
    """Gerencia apenas as tabelas definidas nos nossos modelos, ignorando
    qualquer outro objeto que exista no schema public do Supabase."""
    if type_ == "table":
        return name in target_metadata.tables
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=engine.url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        include_name=include_name,
        include_schemas=False,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_name=include_name,
            include_schemas=False,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
