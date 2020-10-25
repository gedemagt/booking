import os

from dash_extensions.enrich import Dash
from flask import Flask
from flask_user import login_required


import dash_bootstrap_components as dbc

from config import DB_PATH

fapp = Flask(__name__)

fapp.secret_key = os.getenv('SECRET_KEY', 'This is an INSECURE secret!! DO NOT use this in production!!')


fapp.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///" + DB_PATH
fapp.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
fapp.config['MAIL_SERVER'] = 'mail.gandi.net'
fapp.config['MAIL_PORT'] = 587
fapp.config['MAIL_USE_SSL'] = False
fapp.config['MAIL_USE_TLS'] = True
fapp.config['MAIL_USERNAME'] = 'noreply@jeshj.com'
fapp.config['MAIL_PASSWORD'] = os.getenv("SMTP_PASS")
fapp.config['MAIL_DEFAULT_SENDER'] = '"Booking" <noreply@jeshj.com>'

fapp.config['USER_APP_NAME'] = 'Booking'
fapp.config['USER_ENABLE_EMAIL'] = True
fapp.config['USER_ENABLE_USERNAME'] = True
fapp.config['USER_EMAIL_SENDER_NAME'] = 'Booking'
fapp.config['USER_EMAIL_SENDER_EMAIL'] = 'noreply@jeshj.com'

fapp.config['USER_ENABLE_CONFIRM_EMAIL'] = False
fapp.config['USER_ALLOW_LOGIN_WITHOUT_CONFIRMED_EMAIL'] = True

app = Dash(__name__, server=fapp, external_stylesheets=['https://pro.fontawesome.com/releases/v5.10.0/css/all.css', dbc.themes.BOOTSTRAP], title="Booking", update_title=None)
app.suppress_callback_exceptions = True


for view_func in fapp.view_functions:
    if view_func.startswith('/'):
        fapp.view_functions[view_func] = login_required(fapp.view_functions[view_func])