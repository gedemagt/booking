import os

from dash_extensions.enrich import Dash
from flask import Flask
from flask_migrate import Migrate
from flask_user import login_required, allow_unconfirmed_email

import dash_bootstrap_components as dbc

from config import DB_PATH
from models import User, db, init_db
from plugins.admin import init_flask_admin
from plugins.user import CustomUserManager

fapp = Flask(__name__)

fapp.secret_key = os.getenv('SECRET_KEY', 'This is an INSECURE secret!! DO NOT use this in production!!')


fapp.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///" + DB_PATH
fapp.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
fapp.config['MAIL_SERVER'] = os.getenv("SMTP_SERVER")
fapp.config['MAIL_PORT'] = int(os.getenv("PORT", 587))
fapp.config['MAIL_USE_SSL'] = False
fapp.config['MAIL_USE_TLS'] = True
fapp.config['MAIL_USERNAME'] = os.getenv("SMTP_USER")
fapp.config['MAIL_PASSWORD'] = os.getenv("SMTP_PASS")
fapp.config['MAIL_DEFAULT_SENDER'] = '"Booking" <noreply@booking.aarhusklatreklub.dk>'

fapp.config['USER_APP_NAME'] = 'Booking'
fapp.config['USER_ENABLE_EMAIL'] = True
fapp.config['USER_ENABLE_USERNAME'] = True
fapp.config['USER_EMAIL_SENDER_NAME'] = 'Booking'
fapp.config['USER_EMAIL_SENDER_EMAIL'] = 'noreply@booking.aarhusklatreklub.dk'

fapp.config['USER_AFTER_REGISTER_ENDPOINT'] = 'user.resend_email_confirmation'

# fapp.config['USER_ENABLE_CONFIRM_EMAIL'] = False
fapp.config['USER_ALLOW_LOGIN_WITHOUT_CONFIRMED_EMAIL'] = True
# fapp.config['USER_SEND_REGISTERED_EMAIL'] = False

app = Dash(
    __name__,
    server=fapp,
    external_stylesheets=['https://pro.fontawesome.com/releases/v5.10.0/css/all.css', dbc.themes.BOOTSTRAP],
    title="Booking",
    update_title=None,
    suppress_callback_exceptions=True,
)

init_flask_admin(fapp)
user_manager = CustomUserManager(fapp, db, UserClass=User)
init_db(fapp, user_manager)
migrate = Migrate(fapp)


for view_func in fapp.view_functions:
    if view_func.startswith('/'):
        fapp.view_functions[view_func] = allow_unconfirmed_email(login_required(fapp.view_functions[view_func]))