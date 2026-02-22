from __future__ import annotations

import base64
import io
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests


class SharePointDataSource(ABC):
    @abstractmethod
    def load_incidents(self) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def load_observations(self) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def load_exposure(self) -> pd.DataFrame | None:
        raise NotImplementedError


class LocalFileDataSource(SharePointDataSource):
    def __init__(self, local_config: dict):
        self.incident_path = Path(local_config["incident_path"])
        self.observation_path = Path(local_config["observation_path"])
        self.exposure_path = Path(local_config.get("exposure_path", ""))

    @staticmethod
    def _read_file(path: Path) -> pd.DataFrame:
        if path.suffix.lower() in {".xlsx", ".xls"}:
            return pd.read_excel(path)
        return pd.read_csv(path)

    def load_incidents(self) -> pd.DataFrame:
        return self._read_file(self.incident_path)

    def load_observations(self) -> pd.DataFrame:
        return self._read_file(self.observation_path)

    def load_exposure(self) -> pd.DataFrame | None:
        if self.exposure_path and self.exposure_path.exists():
            return self._read_file(self.exposure_path)
        return None


class GraphSharePointDataSource(SharePointDataSource):
    def __init__(self, sp_config: dict):
        self.config = sp_config
        self._token: str | None = None

    def _get_token(self) -> str:
        if self._token:
            return self._token
        import msal

        app = msal.PublicClientApplication(
            client_id=self.config["client_id"],
            authority=self.config["authority"],
        )
        flow = app.initiate_device_flow(scopes=["Files.Read.All", "Sites.Read.All", "offline_access"])
        if "user_code" not in flow:
            raise RuntimeError("Failed to start device code flow")
        print(flow["message"])
        result = app.acquire_token_by_device_flow(flow)
        if "access_token" not in result:
            raise RuntimeError(f"Authentication failed: {result}")
        self._token = result["access_token"]
        return self._token

    def _graph_get(self, endpoint: str, absolute: bool = False) -> dict:
        token = self._get_token()
        url = endpoint if absolute else f"https://graph.microsoft.com/v1.0/{endpoint}"
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def _graph_download(self, endpoint: str, absolute: bool = False) -> bytes:
        token = self._get_token()
        url = endpoint if absolute else f"https://graph.microsoft.com/v1.0/{endpoint}"
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        response.raise_for_status()
        return response.content

    def _read_blob(self, blob: bytes, source_name: str) -> pd.DataFrame:
        stream = io.BytesIO(blob)
        if source_name.lower().endswith((".xlsx", ".xls")):
            return pd.read_excel(stream)
        return pd.read_csv(stream)

    def _read_drive_file(self, file_path: str) -> pd.DataFrame:
        drive_id = self.config.get("document_library_drive_id")
        if not drive_id:
            raise ValueError("document_library_drive_id must be set for file-path downloads")
        endpoint = f"drives/{drive_id}/root:/{quote(file_path)}:/content"
        blob = self._graph_download(endpoint)
        return self._read_blob(blob, file_path)

    def _read_share_url(self, share_url: str, source_name: str) -> pd.DataFrame:
        encoded = base64.urlsafe_b64encode(share_url.encode("utf-8")).decode("utf-8").rstrip("=")
        share_id = f"u!{encoded}"
        endpoint = f"shares/{share_id}/driveItem/content"
        blob = self._graph_download(endpoint)
        return self._read_blob(blob, source_name)

    def _read_document(self, file_path_key: str, file_url_key: str) -> pd.DataFrame:
        file_url = self.config.get(file_url_key)
        file_path = self.config.get(file_path_key)
        if file_url:
            return self._read_share_url(file_url, source_name=file_url)
        if file_path:
            return self._read_drive_file(file_path)
        raise ValueError(f"Missing {file_url_key} or {file_path_key} in configuration")

    def _read_list(self, list_name: str) -> pd.DataFrame:
        site_id = self.config["site_id"]
        endpoint = f"sites/{site_id}/lists/{list_name}/items?expand=fields"
        rows: list[dict] = []
        while endpoint:
            data = self._graph_get(endpoint, absolute=endpoint.startswith("http"))
            rows.extend(item["fields"] for item in data.get("value", []))
            endpoint = data.get("@odata.nextLink")
        return pd.DataFrame(rows)

    def load_incidents(self) -> pd.DataFrame:
        if self.config.get("source_type") == "list":
            return self._read_list(self.config["incident_list_name"])
        return self._read_document("incident_file_path", "incident_file_url")

    def load_observations(self) -> pd.DataFrame:
        if self.config.get("source_type") == "list":
            return self._read_list(self.config["observation_list_name"])
        return self._read_document("observation_file_path", "observation_file_url")

    def load_exposure(self) -> pd.DataFrame | None:
        if self.config.get("source_type") == "list" and self.config.get("exposure_list_name"):
            return self._read_list(self.config["exposure_list_name"])
        if self.config.get("exposure_file_path") or self.config.get("exposure_file_url"):
            return self._read_document("exposure_file_path", "exposure_file_url")
        return None
