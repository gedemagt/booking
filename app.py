import os

from dash import dash
from flask import Flask
from flask_user import login_required


import dash_bootstrap_components as dbc


fapp = Flask(__name__)

fapp.secret_key = os.getenv('SECRET_KEY', 'This is an INSECURE secret!! DO NOT use this in production!!')


fapp.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DB_PATH', 'sqlite:///basic_app.sqlite')
fapp.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
fapp.config['MAIL_SERVER'] = 'in-v3.mailjet.com'
fapp.config['MAIL_PORT'] = 587
fapp.config['MAIL_USE_SSL'] = False
fapp.config['MAIL_USE_TLS'] = True
fapp.config['MAIL_USERNAME'] = '8eace6d92a40609a8cf5b1b096c237c1'
fapp.config['MAIL_PASSWORD'] = "25d77da402c48e68332a4067965d4ade" #os.getenv("SMTP_PASS")
fapp.config['MAIL_DEFAULT_SENDER'] = '"Booking" <noreply@booking.com>'

fapp.config['USER_APP_NAME'] = 'Booking'
fapp.config['USER_ENABLE_EMAIL'] = True
fapp.config['USER_ENABLE_USERNAME'] = True
fapp.config['USER_EMAIL_SENDER_NAME'] = 'Booking'
fapp.config['USER_EMAIL_SENDER_EMAIL'] = 'noreply@booking.com'

fapp.config['USER_ENABLE_CONFIRM_EMAIL'] = False
fapp.config['USER_ALLOW_LOGIN_WITHOUT_CONFIRMED_EMAIL'] = True

app = dash.Dash(server=fapp, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.suppress_callback_exceptions = True


for view_func in fapp.view_functions:
    if view_func.startswith('/'):
        fapp.view_functions[view_func] = login_required(fapp.view_functions[view_func])