# import os
#
#
# class ConfigClass(object):
#     """ Flask application config """
#
#     # Flask settings
#     SECRET_KEY =
#
#     # Flask-SQLAlchemy settings
#     SQLALCHEMY_DATABASE_URI = os.getenv('DB_PATH', 'sqlite:///basic_app.sqlite')  # File-based SQL database
#     SQLALCHEMY_TRACK_MODIFICATIONS = False    # Avoids SQLAlchemy warning
#
#     # Flask-Mail SMTP server settings
#     MAIL_SERVER = 'smtp-relay.sendinblue.com'
#     MAIL_PORT = 587
#     MAIL_USE_SSL = False
#     MAIL_USE_TLS = False
#     MAIL_USERNAME = 'gedemagt@gmail.com'
#     MAIL_PASSWORD = os.getenv("SMTP_PASS")
#     MAIL_DEFAULT_SENDER = '"Booking" <noreply@booking.com>'
#
#     # Flask-User settings
#     USER_APP_NAME = 'Booking'      # Shown in and email templates and page footers
#     USER_ENABLE_EMAIL = True        # Enable email authentication
#     USER_ENABLE_USERNAME = True    # Disable username authentication
#     USER_EMAIL_SENDER_NAME = USER_APP_NAME
#     USER_EMAIL_SENDER_EMAIL = 'noreply@booking.com'
#
#     USER_ENABLE_CONFIRM_EMAIL = False
#     USER_ENABLE_LOGIN_WITHOUT_CONFIRM_EMAIL = True
