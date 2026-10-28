# SYNC SERVICE talk to the central app IN-PROCESS (no network)

from stemmate.services.central_client import CentralClient, CentralError


class CentralTestClient(CentralClient):
    def __init__(self, central_app, key="test-sync-key"):
        self.http = central_app.test_client()
        self.key = key
        self.calls = []                      # (method, path) of every request, for assertions

    def _request(self, method, path, body=None):
        self.calls.append((method, path))
        response = self.http.open(path, method=method, json=body, headers={"X-Sync-Key": self.key})
        if response.status_code >= 400:
            raise CentralError(f"The central store answered {response.status_code}.")
        return response.get_json()

    def unit_puts(self):
        return [path for method, path in self.calls if method == "PUT"]


class OfflineClient(CentralClient):
    # Pretends the network is down.

    def _request(self, method, path, body=None):
        raise CentralError("The central store cannot be reached.")