from pathlib import Path
from typing import List

from src.repository.BaseRepository import BaseRepository


def touch(filepath: str):
    try:
        open(filepath, "x")
    except FileExistsError:
        pass


class SimpleRepository(BaseRepository):
    def __init__(self):
        self._file = Path("ids.txt").absolute()

        touch(self._file)

    def read(self) -> List[int]:
        with open(self._file, "r") as f:
            existing_ids = f.read().strip().split("\n")

        r = [int(id) for id in existing_ids if id is not None and id != ""]

        return r

    def insert_many(self, ids: List[int]) -> None:
        with open(self._file, "a") as f:
            for id in ids:
                f.write(f"{id}\n")

        return None

    def insert(self, id: int) -> None:
        with open(self._file, "a") as f:
            f.write(f"{id}\n")
