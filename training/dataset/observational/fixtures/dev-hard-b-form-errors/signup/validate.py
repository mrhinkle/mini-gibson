def validate(form):
    errors = []
    name = (form.get("name") or "").strip()
    email = (form.get("email") or "").strip()
    if not name:
        errors.append("required")
    if not email:
        errors.append("required")
    elif "@" not in email:
        errors.append("bad")
    return errors
