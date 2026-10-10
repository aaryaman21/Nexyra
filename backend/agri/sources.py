"""Raw adapters; downloaded observation dates never imply historical availability."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid
import httpx
from .data import DataUnavailable, read_prices


def fetch_json(url, params, destination, client=None):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    run = uuid.uuid4().hex
    log = {"id": run, "source": url, "retrieved_at": datetime.now(timezone.utc).isoformat()}
    owned = client is None
    client = client or httpx.Client(timeout=45)
    try:
        response = client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
        (destination / f"{run}.json").write_text(json.dumps({"provenance": log, "data": payload}), encoding="utf-8")
        log["status"] = "success"
        return payload
    except (httpx.HTTPError, ValueError):
        log["status"] = "failed"
        # Never propagate HTTP exception URLs, which can contain credentials.
        raise DataUnavailable("Source request failed; verify availability and credentials") from None
    finally:
        with (destination / "ingestion.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(log)+"\n")
        if owned:
            client.close()


def agmarknet(destination, max_pages=100):
    key, resource = os.getenv("DATA_GOV_IN_API_KEY"), os.getenv("DATA_GOV_IN_RESOURCE_ID")
    if not key or not resource:
        raise DataUnavailable("Configure an API key and verified Data.gov.in resource ID")
    resource = str(uuid.UUID(resource))
    records = []
    for page in range(max_pages):
        data = fetch_json(f"https://api.data.gov.in/resource/{resource}",
                          {"api-key": key, "format": "json", "offset": page*1000, "limit": 1000,
                           "filters[state]": "Maharashtra", "filters[commodity]": "Onion"}, destination)
        batch = data.get("records")
        if not isinstance(batch, list):
            raise DataUnavailable("Unexpected Data.gov.in response")
        records.extend(batch)
        if len(batch) < 1000:
            return records
    raise DataUnavailable("Pagination limit reached; raw pages retained but result is not complete")


def nasa_power(latitude, longitude, start, end, destination):
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Invalid coordinates")
    return fetch_json("https://power.larc.nasa.gov/api/temporal/daily/point",
                      {"latitude": latitude, "longitude": longitude, "start": start, "end": end,
                       "parameters": "T2M,PRECTOTCORR,RH2M", "community": "AG", "format": "JSON"}, destination)


def gdelt(query, destination):
    return fetch_json("https://api.gdeltproject.org/api/v2/doc/doc",
                      {"query": query, "mode": "artlist", "format": "json", "maxrecords": 250,
                       "timespan": "1week", "sort": "datedesc"}, destination)


def coverage(path):
    frame = read_prices(path)
    result = []
    for sid, rows in frame.groupby("series_id"):
        span = int((rows.date.max()-rows.date.min()).days)+1
        median = rows.modal_price.median()
        result.append({"series_id": sid, "market": rows.market.iloc[0], "variety": rows.variety.iloc[0],
                       "start": str(rows.date.min().date()), "end": str(rows.date.max().date()),
                       "observations": len(rows), "calendar_days": span, "coverage": len(rows)/span,
                       "unobserved_days": span-len(rows), "closure_status": "unknown",
                       "extreme_price_flags": int((rows.modal_price > 5*median).sum())})
    return sorted(result, key=lambda r: (-r["observations"], -r["coverage"]))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Assess verified coverage before choosing MVP mandis")
    parser.add_argument("--prices", required=True)
    print(json.dumps(coverage(parser.parse_args().prices), indent=2))
