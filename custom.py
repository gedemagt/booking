from flask_user import UserManager
from flask_user.forms import RegisterForm
from wtforms import StringField, ValidationError

from models import User


class CustomRegisterForm(RegisterForm):
    username = StringField('Username')

    def validate_username(form, field):
        username = field.data
        if User.query.filter_by(username=username).first():
            raise ValidationError('Username already in use')


class CustomUserManager(UserManager):

    def password_validator(self, form, field):
        password = field.data
        print(password)
        if len(password) < 1:
            raise ValidationError('Password must have at least 1 character')

    def customize(self, app):
        self.RegisterFormClass = CustomRegisterForm
