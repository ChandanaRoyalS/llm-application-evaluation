"""The evaluation dataset must always be valid and reproducible."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "eval"))

import validate_dataset  # noqa: E402


def test_dataset_is_valid():
    assert validate_dataset.validate() == []


def test_splits_are_disjoint_and_cover_every_category():
    dev = validate_dataset.load("dev")
    test = validate_dataset.load("test")
    assert not {c["id"] for c in dev} & {c["id"] for c in test}
    assert {c["category"] for c in dev} == validate_dataset.CATEGORIES
    assert {c["category"] for c in test} == validate_dataset.CATEGORIES
