from abc import ABCMeta, abstractmethod
from typing import List


class BaseRepository(metaclass=ABCMeta):
    @abstractmethod
    def read(self) -> List[int]:
        raise NotImplementedError

    @abstractmethod
    def insert_many(self, ids: List[int]) -> None:
        raise NotImplementedError

    @abstractmethod
    def insert(self, id: int) -> None:
        raise NotImplementedError
