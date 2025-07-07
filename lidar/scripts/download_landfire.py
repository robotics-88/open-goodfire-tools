import time, requests, json

# 1) Define endpoints
BASE   = "https://lfps.usgs.gov/arcgis/rest/services/" \
         "LandfireProductService/GPServer/LandfireProductService"
SUBMIT = BASE + "/submitJob"    # note: no trailing slash, no “?f=…” here

JOB    = BASE + "/jobs"

resp = requests.get(SUBMIT, params={
    "f":                "json",
    "Area_Of_Interest": "-105.40207 40.11224 -105.23526 40.19613",
    "Output_Projection":"4326",
    "Layer_List":       "200CC_19;200EVT",
})

print("Status:", resp.status_code)
print("Content-Type:", resp.headers.get("Content-Type"))
print("Body:", resp.text[:500])   # first 500 chars
resp.raise_for_status()
data = resp.json()
print("Submit response:", json.dumps(data, indent=2))

if "error" in data:
    raise RuntimeError(f"Submit failed: {data['error']}")

job_id = data["jobId"]
print(f"Job submitted: {job_id}")

# 4) Poll until complete
status = data["jobStatus"]
while status not in ("esriJobSucceeded", "esriJobFailed"):
    time.sleep(5)
    status_data = requests.get(f"{JOB}/{job_id}", params={"f": "json"}).json()
    status = status_data.get("jobStatus")
    print("  status:", status)

if status != "esriJobSucceeded":
    raise RuntimeError(f"Job {job_id} failed: {status_data}")

# 5) Fetch the output URL
results = status_data["results"]
# There's one output param named "Output_File"
result_info = results["Output_File"]
# The JSON gives you a URL path under paramUrl
param_path = result_info["paramUrl"]       # e.g. "jobs/{jobId}/results/Output_File"
detail = requests.get(f"{BASE}/{param_path}", params={"f": "json"}).json()
zip_url = detail["value"]["url"]
print("Download URL:", zip_url)

# 6) Download the ZIP
zip_resp = requests.get(zip_url, stream=True)
zip_resp.raise_for_status()
with open("landfire_data.zip", "wb") as f:
    for chunk in zip_resp.iter_content(1024*1024):
        f.write(chunk)

print("✅ landfire_data.zip saved")
