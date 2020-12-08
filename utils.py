from flask_login import current_user

from models import Zone


def is_admin():
    return current_user in get_chosen_gym().admins or current_user.role == "ADMIN"


def is_instructor():
    return current_user in get_chosen_gym().instructors


def zone_exists(_id):
    result = Zone.query.filter_by(id=_id).first()
    return result is not None


def get_zone(_id):
    result = Zone.query.filter_by(id=_id).first()
    if result is None:
        return get_chosen_gym().zones[0]
    else:
        return result


def get_chosen_gym():
    return current_user.gyms[0]
