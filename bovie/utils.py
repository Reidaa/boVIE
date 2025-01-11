def touch(filepath: str):
    try:
        open(filepath, "x")
    except FileExistsError:
        pass
