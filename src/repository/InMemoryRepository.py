from typing import List, Set

from src.repository.BaseRepository import BaseRepository


class InMemoryRepository(BaseRepository):
    def __init__(self):
        self.storage: Set[int] = set()

    def read(self) -> List[int]:
        return list(self.storage)

    def insert_many(self, ids: List[int]):
        self._clean()

        for id in ids:
            self.storage.add(id)

    def insert(self, id: int) -> None:
        self._clean()
        self.storage.add(id)

    def _clean(self):
        # Prevent set from growing indefinitely
        if len(self.storage) > 1000:
            self.storage.clear()
