import os

import boto3
from mcp.server import MCPServer

mcp = MCPServer("ec2-ops")
REGION = os.getenv("AWS_REGION", "ap-south-1")
DEFAULT_INSTANCE = os.getenv("EC2_INSTANCE_ID", "")
MOCK = os.getenv("MOCK_MODE", "true").lower() == "true"


def ec2():
    return boto3.client("ec2", region_name=REGION)


@mcp.tool()
def describe_ec2_instance(instance_id: str = "") -> dict:
    """Return EC2 instance metadata and state."""
    instance_id = instance_id or DEFAULT_INSTANCE

    if MOCK:
        return {
            "mode": "mock",
            "instance_id": instance_id or "i-mock123456",
            "state": "running",
            "instance_type": "t3.large",
            "private_ip": "10.0.1.20",
            "availability_zone": f"{REGION}a",
        }

    if not instance_id:
        return {"error": "EC2_INSTANCE_ID is not configured"}

    response = ec2().describe_instances(InstanceIds=[instance_id])
    reservations = response.get("Reservations", [])
    if not reservations or not reservations[0].get("Instances"):
        return {"error": f"Instance {instance_id} not found"}

    i = reservations[0]["Instances"][0]
    return {
        "instance_id": i["InstanceId"],
        "state": i["State"]["Name"],
        "instance_type": i.get("InstanceType"),
        "private_ip": i.get("PrivateIpAddress"),
        "public_ip": i.get("PublicIpAddress"),
        "availability_zone": i.get("Placement", {}).get("AvailabilityZone"),
        "subnet_id": i.get("SubnetId"),
        "vpc_id": i.get("VpcId"),
        "launch_time": i.get("LaunchTime").isoformat()
        if i.get("LaunchTime")
        else None,
    }


@mcp.tool()
def get_ec2_instance_status(instance_id: str = "") -> dict:
    """Return EC2 system and instance status checks."""
    instance_id = instance_id or DEFAULT_INSTANCE

    if MOCK:
        return {
            "mode": "mock",
            "instance_id": instance_id or "i-mock123456",
            "system_status": "ok",
            "instance_status": "ok",
            "reachability": "passed",
        }

    if not instance_id:
        return {"error": "EC2_INSTANCE_ID is not configured"}

    response = ec2().describe_instance_status(
        InstanceIds=[instance_id],
        IncludeAllInstances=True,
    )

    if not response.get("InstanceStatuses"):
        return {"error": f"No status data for {instance_id}"}

    s = response["InstanceStatuses"][0]
    return {
        "instance_id": instance_id,
        "state": s.get("InstanceState", {}).get("Name"),
        "system_status": s.get("SystemStatus", {}).get("Status"),
        "instance_status": s.get("InstanceStatus", {}).get("Status"),
    }


if __name__ == "__main__":
    port = int(os.getenv("MCP_PORT", "8002"))
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=port,
        json_response=True,
        stateless_http=True,
    )
