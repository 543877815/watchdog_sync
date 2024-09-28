from enum import Enum


class OpType(Enum):
    CREATED = 1
    DELETED = 2
    MODIFIED = 3
    MOVED = 4


class ResourceType(Enum):
    FILE = 0
    DIRECTORY = 1


