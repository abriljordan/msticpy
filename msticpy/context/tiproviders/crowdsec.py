# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""
CrowdSec Provider.

Input can be a single IoC observable or a pandas DataFrame containing
multiple observables. Processing may require an API key and
processing performance may be limited to a specific number of
requests per minute for the account type that you have.

"""

from __future__ import annotations

from typing import Any, ClassVar

from typing_extensions import Self

from ..._version import VERSION
from ..http_provider import APILookupParams
from .ti_http_provider import HttpTIProvider
from .ti_provider_base import ResultSeverity

__version__ = VERSION
__author__ = "Shivam Sandbhor"


class CrowdSec(HttpTIProvider):
    """CrowdSec CTI Smoke Lookup."""

    _BASE_URL: ClassVar[str] = "https://cti.api.crowdsec.net"

    _QUERIES: ClassVar[dict[str, APILookupParams]] = {
        "ipv4": APILookupParams(
            path="/v2/smoke/{observable}",
            headers={
                "x-api-key": "{AuthKey}",
                "User-Agent": "crowdsec-msticpy-tiprovider/v1.0.0",
            },
        ),
    }
    _QUERIES["ipv6"] = _QUERIES["ipv4"]

    MEDIUM_SEVERITY: ClassVar[int] = 2
    HIGH_SEVERITY: ClassVar[int] = 3

    def parse_results(self: Self, response: dict) -> tuple[bool, ResultSeverity, Any]:
        """Return the details of the response."""
        if self._failed_response(response):
            return False, ResultSeverity.information, response["RawResult"]["message"]

        if response["RawResult"]["scores"]["overall"]["total"] <= self.MEDIUM_SEVERITY:
            result_severity = ResultSeverity.information
        elif response["RawResult"]["scores"]["overall"]["total"] <= self.HIGH_SEVERITY:
            result_severity = ResultSeverity.warning
        else:
            result_severity = ResultSeverity.high

        return (
            True,
            result_severity,
            {
                "Background Noise": response["RawResult"]["background_noise_score"],
                "Overall Score": response["RawResult"]["scores"]["overall"]["total"],
                "First Seen": response["RawResult"]["history"]["first_seen"],
                "Last Seen": response["RawResult"]["history"]["last_seen"],
                "Attack Details": ",".join(
                    [
                        attack_detail["label"]
                        for attack_detail in response["RawResult"]["attack_details"]
                    ],
                ),
                "Behaviors": ",".join(
                    [
                        behavior["name"]
                        for behavior in response["RawResult"]["behaviors"]
                    ],
                ),
            },
        )
