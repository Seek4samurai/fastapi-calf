def monitor_dev(func):
    def wrapper():
        print("trigger monitor deco")
    return wrapper

def health(func):
    def wrapper():
        print("returning health")
    return wrapper

