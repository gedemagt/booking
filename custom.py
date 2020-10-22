from flask_user import UserManager
from flask_user.forms import RegisterForm
from wtforms import StringField, ValidationError


class CustomRegisterForm(RegisterForm):
    username = StringField('Username')


class CustomUserManager(UserManager):

    def password_validator(self, form, field):
        password = field.data
        if len(password) < 1:
            raise ValidationError('Password must have at least 1 character')

    def customize(self, app):
        self.RegisterFormClass = CustomRegisterForm
