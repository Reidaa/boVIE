from dataclasses import dataclass


@dataclass
class Config:
    token: str
    channel_ID: str
    max_pull: int = 50
