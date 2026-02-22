from __future__ import annotations

import io
from abc import ABC, abstractmethod
from pathlib import Path

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
    GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]

    def __init__(self, sp_config: dict):
        self.config = sp_config
        self._token = None

    def _get_token(self) -> str:
        if self._token:
            return self._token
        import msal

        app = msal.PublicClientApplication(
            client_id=self.config["client_id"],
            authority=self.config["authority"],
        )
        flow = app.initiate_device_flow(scopes=["Sites.Read.All", "Files.Read.All"])
        if "user_code" not in flow:
            raise RuntimeError("Failed to start device code flow")
        print(flow["message"])
        result = app.acquire_token_by_device_flow(flow)
        if "access_token" not in result:
            raise RuntimeError(f"Authentication failed: {result}")
        self._token = result["access_token"]
        return self._token

    def _graph_get(self, endpoint: str) -> dict:
        token = self._get_token()
        response = requests.get(
            f"https://graph.microsoft.com/v1.0/{endpoint}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def _read_drive_file(self, file_path: str) -> pd.DataFrame:
        drive_id = self.config["document_library_drive_id"]
        endpoint = f"drives/{drive_id}/root:/{file_path}:/content"
        token = self._get_token()
        response = requests.get(
            f"https://graph.microsoft.com/v1.0/{endpoint}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        response.raise_for_status()
        blob = io.BytesIO(response.content)
        if file_path.lower().endswith((".xlsx", ".xls")):
            return pd.read_excel(blob)
        return pd.read_csv(blob)

    def _read_list(self, list_name: str) -> pd.DataFrame:
        site_id = self.config["site_id"]
        endpoint = f"sites/{site_id}/lists/{list_name}/items?expand=fields"
        data = self._graph_get(endpoint)
        rows = [item["fields"] for item in data.get("value", [])]
        return pd.DataFrame(rows)

    def load_incidents(self) -> pd.DataFrame:
        if self.config.get("source_type") == "list":
            return self._read_list(self.config["incident_list_name"])
        return self._read_drive_file(self.config["incident_file_path"])

    def load_observations(self) -> pd.DataFrame:
        if self.config.get("source_type") == "list":
            return self._read_list(self.config["observation_list_name"])
        return self._read_drive_file(self.config["observation_file_path"])

    def load_exposure(self) -> pd.DataFrame | None:
        return None
