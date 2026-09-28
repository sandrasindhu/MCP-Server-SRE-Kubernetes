# LangGraph AWS Ops Troubleshooting Agent

A production-style learning project that combines **LangGraph + MCP + AWS CloudWatch + EC2 + EKS + Docker**.

The agent accepts an incident question such as:

> "EKS payments-api pods are returning 5xx. Check the cluster, pods, events, logs and CloudWatch metrics, then explain the likely causes and next troubleshooting steps."

It can use MCP tools to inspect:

- EC2 instance health and metadata
- EC2 CPU utilization from CloudWatch
- CloudWatch alarms
- CloudWatch Logs Insights queries
- EKS cluster state
- EKS nodes
- EKS pods
- Kubernetes events
- Kubernetes pod logs

The project is deliberately designed so beginners can see the complete flow:

```text
User
  |
  v
FastAPI
  |
  v
LangGraph
  |
  +--> Gemini LLM
  |
  +--> MCP Client
         |
         +--> CloudWatch MCP Server
         +--> EC2 MCP Server
         +--> EKS MCP Server
                    |
                    +--> AWS APIs
                    +--> Kubernetes API / kubectl
```

## 1. What you will learn

### AI / Agentic AI

- LangGraph StateGraph
- Agent state
- Tool calling
- Conditional routing
- Tool execution loop
- MCP as the tool/context layer
- Multi-server MCP
- Observability/troubleshooting agent design
- Evidence-first incident analysis

### AWS / SRE

- EC2 troubleshooting
- CloudWatch metrics
- CloudWatch alarms
- CloudWatch Logs Insights
- EKS cluster inspection
- Kubernetes nodes
- Kubernetes pods
- Kubernetes events
- Pod logs
- Common 5xx / CrashLoopBackOff / OOMKilled investigation flow
- IAM and EKS RBAC separation

## 2. Current architecture

The project uses the current MCP Python SDK 2.x line. MCP 2.x renamed the former `FastMCP` high-level server to `MCPServer`; this project follows that API. See the official MCP SDK documentation for the current API and transports.

LangGraph is used for the stateful orchestration loop. MCP servers expose operational tools, while the LangGraph agent decides which tools to call.

## 3. Project structure

```text
langgraph-aws-ops-agent/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── graph.py
│   └── main.py
├── mcp_servers/
│   ├── __init__.py
│   ├── cloudwatch_server.py
│   ├── ec2_server.py
│   └── eks_server.py
├── infra/
│   ├── iam-policy.json
│   └── eks-rbac.yaml
├── tests/
│   └── test_smoke.py
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## 4. Prerequisites

For a real AWS run:

1. AWS account
2. EKS cluster
3. EC2 instance
4. CloudWatch metrics/logs
5. Container Insights enabled for EKS if you want ContainerInsights metrics
6. AWS credentials available to the containers
7. Kubernetes permissions for the identity used by the EKS MCP server
8. Gemini API key

For local learning, you can use `MOCK_MODE=true` and run the entire stack without AWS.

## 5. Why Container Insights matters

For EKS, CloudWatch Container Insights publishes Kubernetes/container metrics in the `ContainerInsights` namespace. If those metrics are not present, verify that Container Insights has been configured.

Typical metrics include CPU, memory, network and failed-node information.

## 6. Configure environment

Copy:

```bash
cp .env.example .env
```

Set:

```env
GEMINI_API_KEY=your_key
AWS_REGION=ap-south-1

EC2_INSTANCE_ID=i-xxxxxxxxxxxxxxxxx
EKS_CLUSTER_NAME=my-eks-cluster

MOCK_MODE=false
```

For a local demo without AWS:

```env
MOCK_MODE=true
GEMINI_API_KEY=your_key
```

## 7. AWS authentication

### Option A - local Docker with AWS profile

The compose file can mount:

```text
~/.aws:/root/.aws:ro
```

Then:

```bash
aws sts get-caller-identity
```

should work on the host.

### Option B - EC2 / ECS / EKS workload identity

For production, prefer IAM roles rather than long-lived access keys.

The container should receive only the permissions it needs.

## 8. IAM

The example `infra/iam-policy.json` contains read-only permissions needed by this project.

It covers:

```text
cloudwatch:GetMetricData
cloudwatch:ListMetrics
cloudwatch:DescribeAlarms
logs:StartQuery
logs:GetQueryResults

ec2:DescribeInstances
ec2:DescribeInstanceStatus

eks:DescribeCluster
eks:ListClusters
eks:DescribeNodegroup
eks:ListNodegroups
```

Important:

**AWS IAM permissions and Kubernetes RBAC permissions are different.**

The EKS server can successfully call:

```text
eks:DescribeCluster
```

and still be unable to list pods if the Kubernetes identity is not authorized inside the cluster.

Use `infra/eks-rbac.yaml` as a learning example. In production, bind only the minimum required permissions.

## 9. Start the project

Build:

```bash
docker compose build
```

Start:

```bash
docker compose up
```

The services are:

```text
agent-api       http://localhost:8080
cloudwatch-mcp  http://localhost:8001/mcp
ec2-mcp         http://localhost:8002/mcp
eks-mcp         http://localhost:8003/mcp
```

Health:

```bash
curl http://localhost:8080/health
```

## 10. Ask the agent a question

```bash
curl -X POST http://localhost:8080/investigate \
  -H "Content-Type: application/json" \
  -d '{
    "query": "EKS payments-api is returning 5xx errors. Check the cluster, pods, events and CloudWatch metrics. Explain the evidence and next troubleshooting steps."
  }'
```

Another example:

```bash
curl -X POST http://localhost:8080/investigate \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Check EC2 CPU utilization for the configured instance and tell me whether CPU saturation could explain the incident."
  }'
```

## 11. The LangGraph workflow

The graph is intentionally simple:

```text
START
  |
  v
agent
  |
  |-- no tool call --> END
  |
  |-- tool call -----> tools
                         |
                         v
                       agent
```

This is the standard tool-calling pattern:

1. LLM receives incident question.
2. LLM decides whether evidence is needed.
3. LangGraph routes tool calls to `ToolNode`.
4. MCP-backed tools execute.
5. Tool results return to the LLM.
6. LLM can call more tools.
7. When enough evidence exists, it produces the incident analysis.

## 12. Why MCP is useful here

Without MCP, the agent code would contain many AWS/Kubernetes-specific integrations.

With MCP:

```text
Agent
  |
  +-- CloudWatch MCP
  +-- EC2 MCP
  +-- EKS MCP
```

Each server has a clear responsibility.

This gives a useful enterprise separation:

```text
AI orchestration      -> LangGraph
Model                 -> Gemini
Tool/context protocol -> MCP
AWS integration       -> boto3
Kubernetes integration-> kubectl
API layer             -> FastAPI
Packaging              -> Docker
```

## 13. MCP tools

### CloudWatch MCP

```text
get_cloudwatch_metric
list_cloudwatch_alarms
query_cloudwatch_logs
```

### EC2 MCP

```text
describe_ec2_instance
get_ec2_instance_status
```

### EKS MCP

```text
describe_eks_cluster
get_eks_nodes
get_eks_pods
get_kubernetes_events
get_pod_logs
```

## 14. Troubleshooting methodology

The system prompt tells the agent to follow an evidence-first process.

### Step 1 - establish scope

Identify:

```text
application
namespace
cluster
region
instance
time window
```

### Step 2 - inspect health

For EKS:

```text
cluster
nodes
pods
events
```

### Step 3 - inspect metrics

Look at:

```text
CPU
memory
failed nodes
network
application metrics
```

### Step 4 - inspect logs

Look for:

```text
ERROR
Exception
timeout
connection refused
OOM
CrashLoopBackOff
5xx
```

### Step 5 - correlate

Example:

```text
5xx
  +
pod restarts
  +
OOMKilled
  +
high memory
```

is stronger evidence than simply seeing high CPU.

### Step 6 - report

The agent should separate:

```text
Observed evidence
Likely interpretation
Unknowns
Next commands/checks
Recommended remediation
```

It should not invent metrics or claim that a root cause was proven when only symptoms were observed.

## 15. Important production safety rule

This project is intentionally **read-only**.

It does not expose destructive tools such as:

```text
delete pod
delete deployment
scale deployment
terminate instance
restart node
modify security group
```

For a real production agent, add human approval before any write operation.

A safe enterprise pattern is:

```text
Detect
  |
  v
Investigate
  |
  v
Generate remediation plan
  |
  v
Human approval
  |
  v
Execute change
  |
  v
Verify
```

## 16. Example incident

Question:

```text
Our checkout service in EKS is returning 502/503.
Investigate it.
```

A useful agent investigation can look like:

```text
1. Check EKS cluster
2. Check nodes
3. Check checkout pods
4. Check Kubernetes events
5. Read recent checkout pod logs
6. Query CloudWatch application/container metrics
7. Correlate evidence
8. Produce findings
```

Possible evidence:

```text
Pod:
checkout-6f9c7d8d7d-x2abc

Status:
CrashLoopBackOff

Events:
Back-off restarting failed container

Logs:
connection refused to database

CloudWatch:
request error rate increased
```

The final response should say that the evidence is consistent with a database connectivity problem, but it should still verify the database endpoint, security rules, DNS and application configuration before declaring root cause.

## 17. Local mock mode

Set:

```env
MOCK_MODE=true
```

This lets students learn the agent loop without an AWS account.

Mock responses simulate:

```text
EC2 CPU
EC2 status
CloudWatch alarms
EKS cluster
EKS nodes
EKS pods
Kubernetes events
pod logs
```

This is useful for classroom demonstrations.

## 18. Useful Docker commands

See running services:

```bash
docker compose ps
```

Logs:

```bash
docker compose logs -f agent
docker compose logs -f eks-mcp
docker compose logs -f cloudwatch-mcp
```

Restart:

```bash
docker compose restart
```

Stop:

```bash
docker compose down
```

Rebuild:

```bash
docker compose build --no-cache
docker compose up
```

## 19. Test MCP servers independently

The MCP endpoints are:

```text
http://localhost:8001/mcp
http://localhost:8002/mcp
http://localhost:8003/mcp
```

Use an MCP-compatible inspector/client to discover and call tools.

The MCP Python SDK supports Streamable HTTP and other standard transports.

## 20. Test the application

Run:

```bash
pytest
```

Or:

```bash
docker compose run --rm agent pytest
```

## 21. Production improvements

For a production implementation, add:

- Amazon Bedrock or another enterprise-approved model
- persistent LangGraph checkpointing
- PostgreSQL
- authentication/authorization
- MCP authentication
- audit logging
- CloudWatch/OpenTelemetry tracing
- rate limiting
- tool timeouts
- retry policies
- structured incident IDs
- Slack/Jira integration
- human approval
- secret management
- least-privilege IAM
- namespace-scoped Kubernetes RBAC
- multi-account AWS support
- multi-region support

## 22. Suggested enterprise evolution

```text
                    +----------------+
                    |   User / SRE   |
                    +-------+--------+
                            |
                            v
                    +----------------+
                    |    FastAPI     |
                    +-------+--------+
                            |
                            v
                    +----------------+
                    |   LangGraph    |
                    | Incident Agent |
                    +-------+--------+
                            |
              +-------------+-------------+
              |             |             |
              v             v             v
        +-----------+ +-----------+ +-----------+
        | CloudWatch| |    EC2    | |    EKS    |
        | MCP       | | MCP       | | MCP       |
        +-----+-----+ +-----+-----+ +-----+-----+
              |             |             |
              v             v             v
        CloudWatch       AWS EC2       EKS/K8s
```

The next level is a multi-agent design:

```text
Supervisor
   |
   +-- EC2 Investigator
   |
   +-- EKS Investigator
   |
   +-- CloudWatch Investigator
   |
   +-- Log Investigator
   |
   +-- Incident Summarizer
```

But start with the single LangGraph agent in this repository. It is easier to debug and teaches the core architecture first.

## 23. Official references

LangGraph:
https://langchain-ai.github.io/langgraph/

MCP Python SDK:
https://py.sdk.modelcontextprotocol.io/

LangChain MCP adapters:
https://reference.langchain.com/python/langchain-mcp-adapters/client/MultiServerMCPClient

AWS CloudWatch GetMetricData:
https://docs.aws.amazon.com/boto3/latest/reference/services/cloudwatch/client/get_metric_data.html

EKS Container Insights metrics:
https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Container-Insights-metrics-EKS.html

## 24. Learning exercise

After starting the project, ask:

```text
1. Check EC2 health.
2. Check CPU for the instance.
3. Check EKS cluster health.
4. Show unhealthy pods.
5. Show recent Kubernetes events.
6. Read logs for a failing pod.
7. Correlate the evidence.
8. Give me a root-cause hypothesis and exactly what I should verify next.
```

Then deliberately introduce a failure in a test EKS workload and run the same investigation again.

That turns this from a simple chatbot into a practical SRE/Agentic-AI lab.
