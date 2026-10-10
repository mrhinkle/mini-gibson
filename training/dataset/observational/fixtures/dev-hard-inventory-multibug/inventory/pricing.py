BULK_THRESHOLD=10
BULK_DISCOUNT=0.1

def line_total(qty, price):
    t=qty*price
    if qty>BULK_THRESHOLD:  # spec: discount applies at >= threshold
        t=t*(1-BULK_DISCOUNT)
    return t
