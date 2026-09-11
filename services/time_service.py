import re


class TimeConverterService:
    # Conversion factors to seconds
    time_units = {
        'ms': 0.001,
        's': 1,
        'm': 60,
        'h': 3600
    }

    @classmethod
    def to_seconds(cls, time_str: str) -> float:
        # Regex to extract value and unit
        match = re.fullmatch(r'([\d.]+)(ms|s|m|h)', time_str.strip().lower())
        if not match:
            raise ValueError(f"Invalid time format: '{time_str}'")

        value, unit = match.groups()
        return float(value) * cls.time_units[unit]