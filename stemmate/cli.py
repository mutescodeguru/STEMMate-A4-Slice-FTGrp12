#ADMIN COMMANDS (no admin screen in A$, AC-8): flask --app stemmate init-db
#Command Line Interface

import click
from flask.cli import with_appcontext

from . import db


@click.command("init-db")   #turns func into command
@with_appcontext
def init_db_command():
    # Create db tables
    db.init_db()
    click.echo("Database Ready!")
    
def register_commands(app):
    app.cli.add_command(init_db_command) 