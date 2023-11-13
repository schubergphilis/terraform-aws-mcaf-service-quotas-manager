import re
from typing import Dict

DICT_PATTERN = re.compile(r"(?<!^)(?=[A-Z])")


def convert_dict(input: Dict) -> Dict:
    return {DICT_PATTERN.sub("_", key).lower(): value for key, value in input.items()}
