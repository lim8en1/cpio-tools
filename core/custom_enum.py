import enum


class CustomEnum(enum.Enum):
    def _generate_next_value_(name, start, count, last_values):
        return name

    @classmethod
    def has_value(cls, value: str) -> bool:
        return value in cls._value2member_map_
