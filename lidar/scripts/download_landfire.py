#!/usr/bin/env python3

import argparse
import time
import requests
import json
import sys

def parse_args():
    p = argparse.ArgumentParser(
        description="Submit a LANDFIRE GPServer job and download the resulting ZIP."
    )
    p.add_argument(
        "--projection", "-p",
        default="4326",
        help="Output projection EPSG code (default: %(default)s)"
    )
    p.add_argument(
        "--output", "-o",
        default="./",
        help="Output directory (default: %(default)s)"
    )
    p.add_argument(
        "--aoi", "-a",
        metavar="XMIN YMIN XMAX YMAX",
        default="-105.40207 40.11224 -105.23526 40.19613",
        help="Area of interest bbox as four floats in a string (default: %(default)s)"
    )
    p.add_argument(
        "--layers", "-l",
        default="ELEV2020;SLPD2020;ASP2020;220F40_22;220CC_22;220CH_22;220CBH_22;220CBD_22",
            # elevation
            # slope degrees
            # aspect
            # fuel models
            # canopy cover
            # canopy height
            # canopy base height
            # canopy bulk density
        help="Semicolon-separated LANDFIRE layer codes (default: %(default)s)"
    )
    return p.parse_args()

def download_flammap_data(crs, aoi, output_dir=".", layers="ELEV2020;SLPD2020;ASP2020;220F40_22;220CC_22;220CH_22;220CBH_22;220CBD_22"):

    BASE   = "https://lfps.usgs.gov/api/job/"
    SUBMIT = BASE + "submit"
    JOBURL = BASE + "status"

    ## TODO did they change the API format? When LANDFIRE server back up, check this:

    submit_params = {
        "f":                  "JSON",              # response format
        "Email":            "example@example.com",
        "Area_of_Interest":             aoi,
        "Output_Projection":       str(crs),
        "Layer_List":       layers
    }

    # submit_params = {
    #     "resample_res":     "30",
    #     "email":            "example@example.com",
    #     "bbox":             aoi,
    #     "output_crs":       str(crs),
    #     "Layer_List":       layers
    # }

    # 1) Submit the job
    resp = requests.get(SUBMIT, params=submit_params)
    print("→ URL   :", resp.url)
    print("→ Code  :", resp.status_code)
    print("→ Type  :", resp.headers.get("Content-Type"))
    resp.raise_for_status()

    data = resp.json()
    if "error" in data:
        print("Submit failed:", json.dumps(data["error"], indent=2), file=sys.stderr)
        sys.exit(1)

    job_id = data["jobId"]
    print(f"Job submitted: {job_id}")

    # 2) Poll until complete
    status = data["status"]
    while status not in ("Succeeded", "Failed"):
        time.sleep(5)
        jr = requests.get(JOBURL, params={"JobId": job_id, "f": "JSON"})
        jr.raise_for_status()
        js = jr.json()
        status = js.get("status", "")
        print("  status:", status)

    if status != "Succeeded":
        print(f"Job {job_id} failed:", json.dumps(js, indent=2), file=sys.stderr)
        sys.exit(1)

    # 3) Get the output ZIP link
    zip_url = js.get("outputFile")
    if not zip_url:
        print("❌ No outputFile found in response:", json.dumps(js, indent=2), file=sys.stderr)
        sys.exit(1)

    print("Download URL:", zip_url)

    # 4) Download the ZIP
    out_fname = f"{output_dir}/landfire_data.zip"
    with requests.get(zip_url, stream=True) as zz:
        zz.raise_for_status()
        with open(out_fname, "wb") as f:
            for chunk in zz.iter_content(1024 * 1024):
                f.write(chunk)

    print(f"✅ Saved to {out_fname}")

if __name__ == "__main__":
    args = parse_args()
    download_flammap_data(args.projection, args.aoi, args.output, args.layers)
