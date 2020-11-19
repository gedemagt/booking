from flask_admin.contrib.sqla import ModelView
from flask import redirect, url_for, request
from flask_login import current_user

from models import User, db, Booking, Gym, Zone
from flask_admin import Admin


class LoggedinModelView(ModelView):

    def is_accessible(self):
        return current_user.is_authenticated and current_user.role == "ADMIN"

    def inaccessible_callback(self, name, **kwargs):
        # redirect to login page if user doesn't have access
        return redirect(url_for('/', next=request.url))


def init_flask_admin(fapp):
    admin = Admin(fapp, name='Booking', template_mode='bootstrap3')
    admin.add_view(LoggedinModelView(User, db.session))
    admin.add_view(LoggedinModelView(Booking, db.session))
    admin.add_view(LoggedinModelView(Gym, db.session))
    admin.add_view(LoggedinModelView(Zone, db.session))
