from abc import ABCMeta, abstractmethod
from typing import List

from src.businessFrance.models import Offer


class BaseWriter(metaclass=ABCMeta):
    @abstractmethod
    def write(self, offer: Offer) -> bool:
        raise NotImplementedError

    @abstractmethod
    def write_many(self, offers: List[Offer]):
        raise NotImplementedError
