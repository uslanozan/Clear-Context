"""Publication metadata parsing never guesses validity, ambiguous formats or current dates."""

import pytest

from clear_context.services.source_time import publication_context


@pytest.mark.parametrize(
    "values,status,dates",
    [
        ([], "missing", []),
        (["Thu, 26 Oct 2023 15:01:52 GMT"], "unambiguous", ["2023-10-26"]),
        (["2023-10-26", "2023-10-26T15:01:52Z"], "unambiguous", ["2023-10-26"]),
        (["2023-10-26", "2024-01-01"], "conflicting", ["2023-10-26", "2024-01-01"]),
        (["03/04/2023"], "unparseable", []),
        (["October 26"], "unparseable", []),
        (["Thu, 26 Oct 0000 15:01:52 GMT"], "unparseable", []),
        (["Thu, 26 Oct 23 1501 GMT"], "unparseable", []),
        (["2023-10-26", "not a date"], "unparseable", ["2023-10-26"]),
    ],
)
def test_explicit_publication_dates(values, status, dates):
    result = publication_context(values)
    assert result.status == status and result.normalized_dates == dates
    assert result.verified is False and result.origin == "search_result_metadata"
