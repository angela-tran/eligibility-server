import csv
import json

import click
from flask import current_app
from flask_sqlalchemy import inspect
import requests

from eligibility_server.db import db
from eligibility_server.db.models import User, Eligibility
from eligibility_server.settings import Configuration


config = Configuration()


@click.command("init-db")
def init_db_command():
    with current_app.app_context():
        inspector = inspect(db.engine)

        if inspector.get_table_names():
            click.echo("Tables already exist.")
            if User.query.count() == 0:
                import_users()
            else:
                click.echo("User table already has data.")
        else:
            click.echo("Creating table...")
            db.create_all()
            click.echo("Table created.")

            import_users()


def import_users():
    """
    Imports user data to database, from either a local or remote JSON or CSV file,
    given the `IMPORT_FILE_PATH` setting.
    CSV files take extra settings: `CSV_DELIMITER`, `CSV_NEWLINE`, `CSV_QUOTING`, `CSV_QUOTECHAR`
    """

    path = config.import_file_path
    click.echo(f"Importing users from: {path}")

    format = path.split(".")[-1].lower()
    remote = path.lower().startswith("http")

    if format not in ["json", "csv"]:
        click.warning(f"File format is not supported: {format}")
        return

    if format == "json":
        import_json_users(path, remote)
    elif format == "csv":
        import_csv_users(path, remote)

    click.echo(f"Users added: {User.query.count()}")
    click.echo(f"Eligibility types added: {Eligibility.query.count()}")


def import_json_users(json_path, remote):
    data = {}
    if remote:
        # download the file to a dict
        data = requests.get(json_path).json()
    else:
        # open the file and load to a dict
        with open(json_path) as file:
            data = json.load(file)
    if "users" in data:
        data = data["users"]
    # unpack from the key/value pairs in data
    # sub = [name, types]
    for sub, (name, types) in data.items():
        save_user(sub, name, types)


def import_csv_users(csv_path, remote):
    if remote:
        # download the entire content as text, split on the lineterminator to a list of rows
        content = requests.get(csv_path).text.strip().split(config.csv_newline)
    else:
        # open the file and read its lines into a list of rows
        with open(csv_path, newline=config.csv_newline, encoding="utf-8") as file:
            content = file.readlines()
    # read rows with reader, saving each user
    data = csv.reader(
        content,
        delimiter=config.csv_delimiter,
        quoting=config.csv_quoting,
        quotechar=config.csv_quotechar,
    )
    for user in data:
        # lists are expected to be a comma-separated value and quoted if the CSV delimiter is a comma
        types = [type.replace(config.csv_quotechar, "") for type in user[2].split(",") if type]
        save_user(user[0], user[1], types)


def save_user(sub: str, name: str, types: str):
    """
    Add a user to the database User table

    @param sub - User's sub
    @param name - User's name
    @param types - Types of eligibilities, in the form of a list of strings
    """

    user = User.query.filter_by(sub=sub, name=name).first() or User(sub=sub, name=name)
    eligibility_types = [Eligibility.query.filter_by(name=type).first() or Eligibility(name=type) for type in types]
    user.types.extend(eligibility_types)

    db.session.add(user)
    db.session.add_all(eligibility_types)

    db.session.commit()


@click.command("drop-db")
def drop_db_command():
    with current_app.app_context():
        inspector = inspect(db.engine)

        if inspector.get_table_names():
            try:
                click.echo(f"Users to be deleted: {User.query.count()}")
                User.query.delete()

                click.echo(f"Eligibility types to be deleted: {Eligibility.query.count()}")
                Eligibility.query.delete()

            except Exception as e:
                click.echo(f"Failed to query models. Exception: {e}", err=True)

            db.session.commit()

            db.drop_all()
            click.echo("Database dropped.")
        else:
            click.echo("Database does not exist.")
