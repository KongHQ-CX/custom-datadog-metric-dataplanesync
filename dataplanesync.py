import os, requests

try:
    # first, try to import the base class from new versions of the Agent
    from datadog_checks.base import AgentCheck
except ImportError:
    # if the above failed, the check is running in Agent version < 6.6.0
    from checks import AgentCheck

# content of the special variable __version__ will be shown in the Agent status page
__version__ = "1.0.0"
__GAUGE__ = "kong.dataplane.is_sync_within_delta"


class KongDataPlaneCheck(AgentCheck):

  def get_actual_hash(self, kong_status_url):
    response = requests.get(
      kong_status_url,
    )

    json_response = response.json()
    return json_response["configuration_hash"]


  def get_expected_hash(self, pat, control_plane_name, konnect_region):
    # Get the control plane ID
    response = requests.get(
      f"https://{konnect_region}.api.konghq.com/v2/control-planes",
      params = {
        "page[size]": "30",
        "page[number]": "1",
        "filter[name][eq]": control_plane_name,
      },
      headers={
        "Authorization": f"Bearer {pat}"
      },
    )

    json_response = response.json()
    if json_response is None:
      return None

    control_plane_id = json_response["data"][0]["id"]

    # Get the expected config hash from Konnect
    response = requests.get(
      f"https://{konnect_region}.api.konghq.com/konnect-api/api/runtime_groups/{control_plane_id}/v1/expected-config-hash",
      headers={"Authorization": f"Bearer {pat}"},
    )

    json_response = response.json()
    if json_response is None:
      return None

    return json_response["expected_hash"]


  def check(self, instance):
    # Setup
    pat = ""
    if "konnect_token" in instance:
      pat = instance["konnect_token"]
    else:
      self.gauge(__GAUGE__, 0)
      raise Exception("[konnect_token] is missing from 'instance' configuration block")

    control_plane_name = ""
    if "konnect_control_plane_name" in instance:
      control_plane_name = instance["konnect_control_plane_name"]
    else:
      self.gauge(__GAUGE__, 0)
      raise Exception("[konnect_control_plane_name] is missing from 'instance' configuration block")

    konnect_region = ""
    if "konnect_region" in instance:
      konnect_region = instance["konnect_region"]
    else:
      self.gauge(__GAUGE__, 0)
      raise Exception("[konnect_region] is missing from 'instance' configuration block")

    # just use default here, if missing
    kong_status_url = "http://127.0.0.1:8100/status"
    if "kong_status_url" in instance:
        kong_status_url = instance["kong_status_url"]

    expected_hash = self.get_expected_hash(pat, control_plane_name, konnect_region)
    if expected_hash is None:
      raise Exception("failed to get EXPECTED HASH from Konnect")

    actual_hash = self.get_actual_hash(kong_status_url)

    if actual_hash is None:
      raise Exception("failed to get ACTUAL HASH from Kong instance")

    # Now calculate the delta and report to Datadawg
    if expected_hash != actual_hash:
      self.gauge(__GAUGE__, 0)
    else:
      self.gauge(__GAUGE__, 1)

if __name__ == '__main__':
  runner = KongDataPlaneCheck(None)
  runner.check()
