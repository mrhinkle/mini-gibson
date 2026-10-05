def process(items):
    out=[]
    for x in items:
        # duplicated normalize logic inline
        y = x.strip().lower()
        if y:
            out.append(y)
    return out

def process_names(names):
    out=[]
    for x in names:
        y = x.strip().lower()
        if y:
            out.append(y)
    return out
