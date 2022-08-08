from flask_sqlalchemy import inspect
from eligibility_server import app
import logging

if __name__ == "__main__":
    inspector = inspect(app.db.engine)

    if inspector.get_table_names():
        logging.info(f"{app.User.query.count()} users to be deleted.")
        app.User.query.delete()
        app.db.session.commit()
        app.db.drop_all()
        logging.info("Database dropped.")
    else:
        logging.info("Database does not exist.")
