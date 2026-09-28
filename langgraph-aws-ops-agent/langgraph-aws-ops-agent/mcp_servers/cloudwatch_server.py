import json
import os
from datetime import datetime, timedelta, timezone

import boto3
from mcp.server import MCPServer

mcp = MCPServer("cloudwatch-ops")
REGION = os.getenv("AWS_REGION", "ap-south-1")
MOCK = os.getenv("MOCK_MODE", "true").lower() == "true"


def cloudwatch():
    return boto3.client("cloudwatch", region_name=REGION)


def logs():
    return boto3.client("logs", region_name=REGION)


@mcp.tool()
def get_cloudwatch_metric(
    namespace: str,
    metric_name: str,
    dimensions: dict[str, str],
    minutes: int = 30,
    statistic: str = "Average",
) -> dict:
    """Read a CloudWatch metric for the last N minutes."""
    if MOCK:
        return {
            "mode": "mock",
            "namespace": namespace,
            "metric_name": metric_name,
            "dimensions": dimensions,
            "statistics": [
                {"timestamp": "mock", "value": 42.5}
            ],
        }

    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=minutes)

    response = cloudwatch().get_metric_data(
        MetricDataQueries=[
            {
                "Id": "m1",
                "MetricStat": {
                    "Metric": {
                        "Namespace": namespace,
                        "MetricName": metric_name,
                        "Dimensions": [
                            {"Name": k, "Value": v}
                            for k, v in dimensions.items()
                        ],
                    },
                    "Period": 60,
                    "Stat": statistic,
                },
                "ReturnData": True,
            }
        ],
        StartTime=start,
        EndTime=end,
        ScanBy="TimestampAscending",
    )

    results = []
    for item in response.get("MetricDataResults", []):
        results.append(
            {
                "label": item.get("Label"),
                "timestamps": [x.isoformat() for x in item.get("Timestamps", [])],
                "values": item.get("Values", []),
                "status": item.get("StatusCode"),
            }
        )

    return {
        "mode": "aws",
        "namespace": namespace,
        "metric_name": metric_name,
        "dimensions": dimensions,
        "results": results,
    }


@mcp.tool()
def list_cloudwatch_alarms() -> dict:
    """List CloudWatch alarms and their current states."""
    if MOCK:
        return {
            "mode": "mock",
            "alarms": [
                {"name": "MockHighCPU", "state": "OK"},
                {"name": "Mock5xxAlarm", "state": "ALARM"},
            ],
        }

    response = cloudwatch().describe_alarms()
    alarms = []
    for alarm in response.get("MetricAlarms", []):
        alarms.append(
            {
                "name": alarm.get("AlarmName"),
                "state": alarm.get("StateValue"),
                "reason": alarm.get("StateReason"),
                "updated": alarm.get("StateUpdatedTimestamp").isoformat()
                if alarm.get("StateUpdatedTimestamp")
                else None,
            }
        )
    return {"mode": "aws", "alarms": alarms}


@mcp.tool()
def query_cloudwatch_logs(
    log_group_name: str,
    query: str,
    minutes: int = 30,
) -> dict:
    """Run a CloudWatch Logs Insights query over the last N minutes."""
    if MOCK:
        return {
            "mode": "mock",
            "log_group": log_group_name,
            "query": query,
            "results": [
                {"@timestamp": "mock", "@message": "ERROR connection refused"}
            ],
        }

    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=minutes)

    started = logs().start_query(
        logGroupName=log_group_name,
        startTime=int(start.timestamp()),
        endTime=int(end.timestamp()),
        queryString=query,
    )

    import time
    query_id = started["queryId"]

    for _ in range(20):
        response = logs().get_query_results(queryId=query_id)
        if response["status"] in {"Complete", "Failed", "Cancelled", "Timeout"}:
            rows = []
            for result in response.get("results", []):
                rows.append({x["field"]: x.get("value") for x in result})
            return {
                "mode": "aws",
                "status": response["status"],
                "results": rows,
            }
        time.sleep(1)

    return {"mode": "aws", "status": "Timeout", "results": []}


if __name__ == "__main__":
    port = int(os.getenv("MCP_PORT", "8001"))
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=port,
        json_response=True,
        stateless_http=True,
    )
