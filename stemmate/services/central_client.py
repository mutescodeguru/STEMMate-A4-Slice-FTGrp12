# LOCAL APP TALKS to the central store. The sync service only uses the three methods of CentralClient, so tests can swap in a fake connection.

import json
import urllib.error
import urllib.request


class CentralError(Exception):
    """ Any problem reaching or using the central store (offline, refused, outage) """


class CentralClient:
    # The three calls from P1's contract. Subclasses implement _request.

    def _request(self, method, path, body=None):
        raise NotImplementedError

    def progress(self, plan_id, version):
        return self._request("GET", f"/central/plans/{plan_id}/progress?version={version}")

    def put_unit(self, plan_id, index, version, unit_count, payload):
        return self._request("PUT", f"/central/plans/{plan_id}/units/{index}",
                             {"version": version, "unit_count": unit_count, "payload": payload})

    def commit(self, plan_id, version, unit_count):
        return self._request("POST", f"/central/plans/{plan_id}/commit",
                             {"version": version, "unit_count": unit_count})


class HttpCentralClient(CentralClient):
    # Real network calls using only Python's standard library

    def __init__(self, base_url, sync_key, timeout=5):
        self.base_url = base_url.rstrip("/")
        self.sync_key = sync_key
        self.timeout = timeout

    def _request(self, method, path, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            self.base_url + path, data=data, method=method,
            headers={"Content-Type": "application/json", "X-Sync-Key": self.sync_key})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as err:        # the server answered with an error code
            raise CentralError(f"The central store answered {err.code}.") from None
        except (urllib.error.URLError, TimeoutError, OSError):   # no connection at all
            raise CentralError("The central store cannot be reached.") from None