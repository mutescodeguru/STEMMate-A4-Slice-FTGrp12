#ADMIN COMMANDS (no admin screen in A$, AC-8): flask --app stemmate init-db
#Command Line Interface

import click
from flask.cli import with_appcontext

from . import db
from .services import auth_service


@click.command("init-db")
@with_appcontext
def init_db_command():
    # Create the database tables
    db.init_db()
    click.echo("Database ready.")


@click.command("create-user")
@click.argument("username")
@click.password_option() # asks twice, hides what you type
@with_appcontext
def create_user_command(username, password):
    # Create a facilitator account
    try:
        auth_service.create_user(db.get_db(), username, password)
    except ValueError as err:
        raise click.ClickException(str(err))
    click.echo(f"Created user '{username.strip()}'.")


def register_commands(app):
    app.cli.add_command(init_db_command)
    app.cli.add_command(create_user_command)