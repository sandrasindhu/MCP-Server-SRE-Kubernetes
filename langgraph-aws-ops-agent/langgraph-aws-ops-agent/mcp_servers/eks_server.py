import json
import os
import subprocess

import boto3
from mcp.server import MCPServer

mcp = MCPServer("eks-ops")

REGION = os.getenv("AWS_REGION", "ap-south-1")
CLUSTER = os.getenv("EKS_CLUSTER_NAME", "")
NAMESPACE = os.getenv("EKS_NAMESPACE", "default")
MOCK = os.getenv("MOCK_MODE", "true").lower() == "true"


def eks():
    return boto3.client("eks", region_name=REGION)


def run_kubectl(args: list[str]) -> dict:
    command = ["kubectl"] + args
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=30,
    )

    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout[-30000:],
        "stderr": completed.stderr[-10000:],
        "command": " ".join(command),
    }


@mcp.tool()
def describe_eks_cluster(cluster_name: str = "") -> dict:
    """Describe EKS cluster status, endpoint and Kubernetes version."""
    cluster_name = cluster_name or CLUSTER

    if MOCK:
        return {
            "mode": "mock",
            "name": cluster_name or "mock-eks",
            "status": "ACTIVE",
            "version": "1.33",
            "endpoint": "https://mock.eks.local",
        }

    if not cluster_name:
        return {"error": "EKS_CLUSTER_NAME is not configured"}

    c = eks().describe_cluster(name=cluster_name)["cluster"]
    return {
        "name": c.get("name"),
        "status": c.get("status"),
        "version": c.get("version"),
        "endpoint": c.get("endpoint"),
        "platform_version": c.get("platformVersion"),
        "created_at": c.get("createdAt").isoformat()
        if c.get("createdAt")
        else None,
    }


@mcp.tool()
def get_eks_nodes() -> dict:
    """List Kubernetes nodes and their readiness information."""
    if MOCK:
        return {
            "mode": "mock",
            "nodes": [
                {"name": "ip-10-0-1-10", "status": "Ready", "cpu": "8", "memory": "32Gi"},
                {"name": "ip-10-0-2-10", "status": "Ready", "cpu": "8", "memory": "32Gi"},
            ],
        }

    return run_kubectl(
        ["get", "nodes", "-o", "wide", "--show-labels"]
    )


@mcp.tool()
def get_eks_pods(
    namespace: str = "",
    label_selector: str = "",
) -> dict:
    """List Kubernetes pods with status and restart counts."""
    namespace = namespace or NAMESPACE

    if MOCK:
        return {
            "mode": "mock",
            "namespace": namespace,
            "pods": [
                {
                    "name": "payments-api-6f9c7d8d7d-x2abc",
                    "ready": "1/1",
                    "status": "Running",
                    "restarts": 0,
                },
                {
                    "name": "payments-api-6f9c7d8d7d-x2def",
                    "ready": "0/1",
                    "status": "CrashLoopBackOff",
                    "restarts": 8,
                },
            ],
        }

    args = ["get", "pods", "-n", namespace, "-o", "wide"]
    if label_selector:
        args.extend(["-l", label_selector])
    return run_kubectl(args)


@mcp.tool()
def get_kubernetes_events(namespace: str = "") -> dict:
    """Return recent Kubernetes events for an investigation."""
    namespace = namespace or NAMESPACE

    if MOCK:
        return {
            "mode": "mock",
            "events": [
                {
                    "type": "Warning",
                    "reason": "BackOff",
                    "object": "pod/payments-api-6f9c7d8d7d-x2def",
                    "message": "Back-off restarting failed container",
                },
                {
                    "type": "Warning",
                    "reason": "Unhealthy",
                    "object": "pod/payments-api-6f9c7d8d7d-x2def",
                    "message": "Readiness probe failed",
                },
            ],
        }

    return run_kubectl(
        [
            "get",
            "events",
            "-n",
            namespace,
            "--sort-by=.lastTimestamp",
        ]
    )


@mcp.tool()
def get_pod_logs(
    pod_name: str,
    namespace: str = "",
    tail_lines: int = 200,
    container: str = "",
) -> dict:
    """Read recent logs from a Kubernetes pod."""
    namespace = namespace or NAMESPACE

    if MOCK:
        return {
            "mode": "mock",
            "pod": pod_name,
            "logs": (
                "2026-09-25T09:30:01 ERROR database connection refused\n"
                "2026-09-25T09:30:02 ERROR retrying database connection\n"
                "2026-09-25T09:30:05 ERROR application startup failed\n"
            ),
        }

    args = [
        "logs",
        pod_name,
        "-n",
        namespace,
        "--tail",
        str(tail_lines),
        "--timestamps",
    ]
    if container:
        args.extend(["-c", container])

    return run_kubectl(args)


if __name__ == "__main__":
    port = int(os.getenv("MCP_PORT", "8003"))
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=port,
        json_response=True,
        stateless_http=True,
    )
