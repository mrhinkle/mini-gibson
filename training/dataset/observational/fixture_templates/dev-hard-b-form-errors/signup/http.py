from .validate import validate


def handle(form):
    errs = validate(form)
    if not errs:
        return 200, {"ok": True}
    if "required" in errs:
        return 400, {"errors": errs}
    return 200, {"ok": True}
