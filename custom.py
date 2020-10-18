from flask_user import UserManager
from flask_user.forms import RegisterForm
from wtforms import StringField


class CustomRegisterForm(RegisterForm):
    username = StringField('Username')


class CustomUserManager(UserManager):
    def customize(self, app):
        self.RegisterFormClass = CustomRegisterForm
