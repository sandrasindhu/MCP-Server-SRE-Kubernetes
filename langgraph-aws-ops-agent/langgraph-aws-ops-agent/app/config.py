import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    aws_region: str = os.getenv("AWS_REGION", "ap-south-1")
    ec2_instance_id: str = os.getenv("EC2_INSTANCE_ID", "")
    eks_cluster_name: str = os.getenv("EKS_CLUSTER_NAME", "")
    eks_namespace: str = os.getenv("EKS_NAMESPACE", "default")
    eks_pod_name: str = os.getenv("EKS_POD_NAME", "")
    cloudwatch_log_group: str = os.getenv("CLOUDWATCH_LOG_GROUP", "")
    lookback_minutes: int = int(os.getenv("LOOKBACK_MINUTES", "30"))
    mock_mode: bool = os.getenv("MOCK_MODE", "true").lower() == "true"


settings = Settings()
