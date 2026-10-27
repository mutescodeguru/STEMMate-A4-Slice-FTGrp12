#ADMIN COMMANDS (no admin screen in A$, AC-8): flask --app stemmate init-db

#     flask --app stemmate init-db
#     flask --app stemmate create-user alice
#     flask --app stemmate seed-materials

import click
from flask.cli import with_appcontext

from . import db, seed_data
from .services import auth_service


@click.command("init-db")
@with_appcontext
def init_db_command():
    # Create the database tables.
    db.init_db()
    click.echo("Database ready.")


@click.command("create-user")
@click.argument("username")
@click.password_option() # asks twice, hides what you type
@with_appcontext
def create_user_command(username, password):
    # Create a facilitator account.
    try:
        auth_service.create_user(db.get_db(), username, password)
    except ValueError as err:
        raise click.ClickException(str(err))
    click.echo(f"Created user '{username.strip()}'.")


@click.command("seed-materials")
@with_appcontext
def seed_materials_command():
    # Load the synthetic materials catalogue.
    total = seed_data.seed_materials(db.get_db())
    click.echo(f"Materials in the database: {total}")


def register_commands(app):
    app.cli.add_command(init_db_command)
    app.cli.add_command(create_user_command)
    app.cli.add_command(seed_materials_command)