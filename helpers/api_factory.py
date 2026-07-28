#### call fully geneerated by API and tweaked by yours truely.  Gotta say, AI is a time saver!

from typing import Any, Optional

import requests
import json
from requests import Response, Session


class APIClientError(Exception):
    """Raised when an API request fails."""


class APIClient:
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        api_key_header: str = "X-API-Key",
        bearer_token: Optional[str] = None,
        timeout: int = 30,
        logger=None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.logger = logger
        self.session = Session()

        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

        if api_key:
            self.session.headers[api_key_header] = api_key

        if bearer_token:
            self.session.headers["Authorization"] = (
                f"Bearer {bearer_token}"
            )

    def _build_url(self, endpoint: str) -> str:
        """
        Convert an endpoint into a complete URL.
        """
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def _log(self, level: str, message: str) -> None:
        """
        Write to the configured logger when available.
        """
        if self.logger is None:
            return

        try:
            self.logger.log_to_file(
                level,
                [message],
            )
        except Exception:
            # Logging errors should not hide the original API error.
            pass

    def _handle_response(self, response: Response) -> Any:
        """
        Check for HTTP errors and return decoded JSON.
        """
        try:
            response.raise_for_status()

        except requests.HTTPError as exc:
            try:
                error_details = response.json()
            except ValueError:
                error_details = response.text

            error_message = (
                "API request failed.\n"
                f"Status: {response.status_code}\n"
                f"URL: {response.url}\n"
                f"Response: {error_details}"
            )

            #self._log("ERROR", error_message)

            raise APIClientError(error_message) from exc

        # DELETE, PATCH, and other successful requests may return no body.
        if response.status_code == 204 or not response.content:
            return None

        try:
            return response.json()

        except ValueError as exc:
            error_message = (
                "API returned a non-JSON response.\n"
                f"Status: {response.status_code}\n"
                f"URL: {response.url}\n"
                f"Response: {response.text}"
            )

            self._log("ERROR", error_message)

            raise APIClientError(error_message) from exc

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        json_data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Send an HTTP request and process the response.
        """
        url = self._build_url(endpoint)

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                timeout=self.timeout,
            )

        except requests.RequestException as exc:
            error_message = (
                "Unable to connect to API.\n"
                f"Method: {method.upper()}\n"
                f"URL: {url}\n"
                f"Error: {exc}"
            )

            self._log("CRITICAL", error_message)

            raise APIClientError(error_message) from exc

        return self._handle_response(response)

    def get(
        self,
        endpoint: str,
        
        json_data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Send a GET request.

        Example:
            client.get(
                "/api/v1/members",
                params={
                    "limit": 100,
                    "offset": 0,
                },
            )
        """
        return self._request(
            "GET",
            endpoint,
            json_data=json_data,
            params=params,
        )

    def post(
        self,
        endpoint: str,
        json_data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Send a POST request with an optional JSON body.

        Example:
            client.post(
                "/api/v1/members/create",
                json_data={
                    "character_name": "Paxxar",
                    "level": 60,
                },
            )
        """
        return self._request(
            "POST",
            endpoint,
            json_data=json_data,
            params=params,
        )

    def patch(
        self,
        endpoint: str,
        json_data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Send a PATCH request with an optional JSON body.

        Example:
            client.patch(
                "/api/v1/members/5",
                json_data={
                    "level": 60,
                    "rank": "raider",
                    "active": True,
                },
            )
        """
        #print(json_data)
        #print(json.dumps(json_data, indent=2))
        return self._request(
            "PATCH",
            endpoint,
            json_data=json_data,
            params=params,
        )

    def close(self) -> None:
        """
        Close the reusable HTTP session.
        """
        self.session.close()

    def __enter__(self) -> "APIClient":
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        self.close()