# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""
Module for ContextProvider classes.

Input can be a single observable or a pandas DataFrame containing
multiple observables. Processing may require a an API key and
processing performance may be limited to a specific number of
requests per minute for the account type that you have.

"""
from __future__ import annotations

import re
from abc import abstractmethod
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import TYPE_CHECKING, Any, ClassVar, Iterable

from typing_extensions import Self

from ..._version import VERSION
from ...common.utility import export
from ..lookup_result import SanitizedObservable
from ..provider_base import Provider

if TYPE_CHECKING:
    import pandas as pd
__version__ = VERSION
__author__ = "Ian Hellen"

# Regular expression from Grok patterns
# https://github.com/hpcugent/logstash-patterns/blob/master/files/grok-patterns
HOSTNAME_REGEX: str = (
    r"\b(?:[0-9A-Za-z][0-9A-Za-z-]{0,62})"
    r"(?:\.(?:[0-9A-Za-z][0-9A-Za-z-]{0,62}))*(\.?|\b)"
)


def _validate_hostname(hostname: str) -> SanitizedObservable:
    """Validate that parameter is a valid hostname."""
    match_hostname: re.Match | None = re.compile(
        HOSTNAME_REGEX,
        re.IGNORECASE | re.VERBOSE | re.MULTILINE,
    ).search(hostname)
    if not match_hostname:
        return SanitizedObservable(None, "Unrecognized hostname")

    return SanitizedObservable(match_hostname.group(0), "ok")


def _validate_ip(
    ipaddress: str,
    version: int = 4,
) -> SanitizedObservable:
    """Ensure Ip address is a valid public IPv4 address."""
    try:
        addr: IPv4Address | IPv6Address = ip_address(ipaddress)
    except ValueError:
        return SanitizedObservable(None, "IP address is invalid format")

    if version == addr.version and not isinstance(
        addr,
        IPv4Address,
    ):
        return SanitizedObservable(None, "Not an IPv4 address")
    if version == addr.version and not isinstance(
        addr,
        IPv6Address,
    ):
        return SanitizedObservable(None, "Not an IPv6 address")

    return SanitizedObservable(ipaddress, "ok")


@export
class ContextProvider(Provider):
    """Abstract base class for Context providers."""

    _REQUIRED_PARAMS: ClassVar[list[str]] = []

    def __init__(self: ContextProvider) -> None:
        """Initialize Context provider."""
        super().__init__()
        self._preprocessors.processors.pop("hostname")
        self._preprocessors.processors.pop("ipv4")
        self._preprocessors.processors.pop("ipv6")
        self._preprocessors.add_check("hostname", _validate_hostname)
        self._preprocessors.add_check("ipv4", _validate_ip)
        self._preprocessors.add_check("ipv6", _validate_ip)

    def lookup_item(
        self: Self,
        item: str,
        item_type: str | None = None,
        query_type: str | None = None,
    ) -> pd.DataFrame:
        """
        Lookup from a value.

        Parameters
        ----------
        item : str
            item to lookup
        item_type : str, optional
            The Type of the item to lookup, by default None (type will be inferred)
        query_type : str, optional
            Specify the data subtype to be queried, by default None.
            If not specified the default record type for the item_value
            will be returned.

        Returns
        -------
        pd.DataFrame
            The lookup result:
            result - Positive/Negative,
            details - Lookup Details (or status if failure),
            raw_result - Raw Response
            reference - URL of the item

        Raises
        ------
        NotImplementedError
            If attempting to use an HTTP method or authentication
            protocol that is not supported.

        Notes
        -----
        Note: this method uses memoization (lru_cache) to cache results
        for a particular observable to try avoid repeated network calls for
        the same item.

        """
        return self.lookup_observable(
            observable=item,
            observable_type=item_type,
            query_type=query_type,
        )

    @abstractmethod
    def lookup_observable(
        self: Self,
        observable: str,
        observable_type: str | None = None,
        query_type: str | None = None,
    ) -> pd.DataFrame:
        """
        Lookup a single observable.

        Parameters
        ----------
        observable : str
            Observable value to lookup
        observable_type : str, optional
            The Type of the value to lookup, by default None (type will be inferred)
        query_type : str, optional
            Specify the data subtype to be queried, by default None.
            If not specified the default record type for the item_value
            will be returned.

        Returns
        -------
        pd.DataFrame
            The context lookup result:
            result - Positive/Negative,
            details - Lookup Details (or status if failure),
            raw_result - Raw Response
            reference - URL of the item

        """

    def _check_item_type(
        self: Self,
        item: str,
        item_type: str | None = None,
        query_subtype: str | None = None,
    ) -> dict:
        """
        Check Item Type and cleans up item.

        Parameters
        ----------
        item : str
            item
        item_type : str, optional
            item type, by default None
        query_subtype : str, optional
            Query sub-type, if any, by default None

        Returns
        -------
        dict
            Dict result with resolved type and pre-processed item.
            Status is none-zero on failure.

        """
        return self._check_observable_type(
            item,
            item_type,
            query_subtype,
        )

    def _check_observable_type(
        self: Self,
        obs: str,
        obs_type: str | None = None,
        query_subtype: str | None = None,
    ) -> dict:
        """
        Check Observable Type and cleans up observable.

        Parameters
        ----------
        obs : str
            Observable
        obs_type : str, optional
            Observable type, by default None
        query_subtype : str, optional
            Query sub-type, if any, by default None

        Returns
        -------
        dict
            Dict result with resolved type and pre-processed Observable.
            Status is none-zero on failure.

        """
        result: dict[str, Any] = super()._check_item_type(
            item=obs,
            item_type=obs_type,
            query_subtype=query_subtype,
        )
        result["Observable"] = result.pop("Item")
        result["ObservableType"] = result.pop("ItemType")
        result["SafeObservable"] = result.pop("SanitizedValue")
        return result

    @abstractmethod
    def parse_results(self: Self, response: dict) -> tuple[bool, Any]:
        """
        Return the details of the response.

        Parameters
        ----------
        response : dict
            The returned data response

        Returns
        -------
        tuple[bool, ResultSeverity, Any]
            bool = positive or negative hit
            ResultSeverity = enumeration of severity
            Object with match details

        """

    def lookup_observables(
        self: Self,
        data: pd.DataFrame | dict[str, str] | Iterable[str],
        obs_col: str | None = None,
        obs_type_col: str | None = None,
        query_type: str | None = None,
    ) -> pd.DataFrame:
        """
        Lookup collection of observables.

        Parameters
        ----------
        data : pd.DataFrame | dict[str, str] | Iterable[str]
            Data input in one of three formats:
            1. Pandas dataframe (you must supply the column name in
            `obs_col` parameter)
            2. Dict of observables
            3. Iterable of observables
        obs_col : str, optional
            DataFrame column to use for observables, by default None
        obs_type_col : str, optional
            DataFrame column to use for observables types, by default None
        query_type : str, optional
            Specify the data subtype to be queried, by default None.
            If not specified the default record type for the type
            will be returned.

        Returns
        -------
        pd.DataFrame
            DataFrame of results.

        """
        return self.lookup_items(
            data,
            item_col=obs_col,
            item_type_col=obs_type_col,
            query_type=query_type,
        )

    async def lookup_observables_async(
        self: Self,
        data: pd.DataFrame | dict[str, str] | Iterable[str],
        obs_col: str | None = None,
        obs_type_col: str | None = None,
        query_type: str | None = None,
    ) -> pd.DataFrame:
        """Call base async wrapper."""
        return await self._lookup_items_async_wrapper(
            data,
            item_col=obs_col,
            item_type_col=obs_type_col,
            query_type=query_type,
        )

    async def _lookup_observables_async_wrapper(
        self: Self,
        data: pd.DataFrame | dict[str, str] | Iterable[str],
        obs_col: str | None = None,
        obs_type_col: str | None = None,
        query_type: str | None = None,
    ) -> pd.DataFrame:
        """
        Async wrapper for providers that do not implement lookup_iocs_async.

        Parameters
        ----------
        data : pd.DataFrame | dict[str, str] | Iterable[str]
            Data input in one of three formats:
            1. Pandas dataframe (you must supply the column name in
            `obs_col` parameter)
            2. Dict of observable, Observables Types
            3. Iterable of observables - Observables Types will be inferred
        obs_col : str, optional
            DataFrame column to use for observables, by default None
        obs_type_col : str, optional
            DataFrame column to use for Observables Types, by default None
        query_type : str, optional
            Specify the data subtype to be queried, by default None.
            If not specified the default record type for the IoC type
            will be returned.

        Returns
        -------
        pd.DataFrame
            DataFrame of results.

        """
        return await self._lookup_items_async_wrapper(
            data,
            item_col=obs_col,
            item_type_col=obs_type_col,
            query_type=query_type,
        )
