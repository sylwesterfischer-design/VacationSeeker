from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import RawOffer


class BaseCollector(ABC):
    source_name: str

    @abstractmethod
    def collect(self) -> list[RawOffer]:
        raise NotImplementedError

