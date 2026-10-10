def gcd(a,b):
    # BUG: broken euclid
    while b:
        a=b
        b=a%b
    return a
