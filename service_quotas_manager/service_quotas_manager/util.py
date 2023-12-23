import re
from typing import Dict

from aws_lambda_powertools import Logger

DICT_PATTERN = re.compile(r"(?<!^)(?=[A-Z])")

logger = Logger()


def convert_dict(input: Dict) -> Dict:
    return {DICT_PATTERN.sub("_", key).lower(): value for key, value in input.items()}
