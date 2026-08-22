from main import health

@health
def home():
    return {"status": "done"}


if __name__ == "__main__":
    home()
