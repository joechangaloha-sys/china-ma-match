from alembic import context

connection = context.config.attributes['connection']
context.configure(connection=connection, transactional_ddl=connection.dialect.name=='postgresql')
with context.begin_transaction():
    context.run_migrations()
