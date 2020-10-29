from flask_login import current_user


def is_admin():
    return current_user in get_chosen_gym().admins or current_user.role == "ADMIN"


def get_chosen_gym():
    return current_user.gyms[0]
