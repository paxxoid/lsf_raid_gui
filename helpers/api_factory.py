from typing import Any, Optional

import requests
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
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
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
            self.session.headers["Authorization"] = f"Bearer {bearer_token}"

    def _build_url(self, endpoint: str) -> str:
        """
        Converts an endpoint such as /api/v1/members into a complete URL.
        """
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def _handle_response(self, response: Response) -> Any:
        """
        Checks for HTTP errors and returns the decoded JSON response.
        """
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            try:
                error_details = response.json()
            except ValueError:
                error_details = response.text

            raise APIClientError(
                f"API request failed.\n"
                f"Status: {response.status_code}\n"
                f"URL: {response.url}\n"
                f"Response: {error_details}"
            ) from exc

        # Some successful requests, such as DELETE, may return no content.
        if response.status_code == 204 or not response.content:
            return None

        try:
            return response.json()
        except ValueError as exc:
            raise APIClientError(
                f"API returned a non-JSON response.\n"
                f"Status: {response.status_code}\n"
                f"URL: {response.url}\n"
                f"Response: {response.text}"
            ) from exc

    def get(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Sends a GET request.

        Example:
            client.get(
                "/api/v1/members",
                params={"limit": 100, "offset": 0}
            )
        """
        url = self._build_url(endpoint)

        try:
            response = self.session.get(
                url,
                params=params,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise APIClientError(f"Unable to connect to {url}: {exc}") from exc

        return self._handle_response(response)

    def post(
        self,
        endpoint: str,
        json_data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Sends a POST request with a JSON body.

        Example:
            client.post(
                "/api/v1/members/create",
                json_data={
                    "character_name": "Paxxar",
                    "level": 60
                }
            )
        """
        url = self._build_url(endpoint)

        try:
            response = self.session.post(
                url,
                params=params,
                json=json_data,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise APIClientError(f"Unable to connect to {url}: {exc}") from exc

        return self._handle_response(response)

    def close(self) -> None:
        """
        Closes the reusable HTTP session.
        """
        self.session.close()

    def __enter__(self) -> "APIClient":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()