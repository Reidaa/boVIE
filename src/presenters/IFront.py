from abc import ABCMeta, abstractmethod
from typing import List
from src.businessFrance.models import Offer


class IFront(metaclass=ABCMeta):
    @abstractmethod
    def print(self, offer: Offer) -> List[int]:
        raise NotImplementedError
