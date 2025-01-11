from pathlib import Path
from typing import List

from bovie.utils import touch


class OfferRepository:
    def __init__(self):
        self._file = Path("ids.txt").absolute()

        touch(self._file)

    def read(self) -> List[int]:
        with open(self._file, "r") as f:
            exising_ids = f.read().strip().split("\n")

        r = [int(id) for id in exising_ids if id is not None and id != ""]

        return r

    def insert_many(self, ids: List[int]) -> None:
        with open(self._file, "a") as f:
            for id in ids:
                f.write(f"{id}\n")

        return None
