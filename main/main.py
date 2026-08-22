from functools import wraps

def monitor_dev(func):
    def wrapper():
        print("trigger monitor deco")
    return wrapper


def health(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        print("returning health")
        return func(*args, **kwargs)

    return wrapper
