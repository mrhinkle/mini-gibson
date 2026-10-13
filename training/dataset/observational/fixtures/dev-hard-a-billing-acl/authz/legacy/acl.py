"""Legacy ACL."""


def allowed(role, action):
    return role == "admin"
