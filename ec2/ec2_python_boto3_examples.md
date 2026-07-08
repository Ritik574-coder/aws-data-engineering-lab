# EC2 — Python Boto3 Examples

## Service Overview

Boto3 EC2 client for automating instance lifecycle, tagging, and fleet management in data pipelines.

---

## Production Example — Launch Spot Fleet Worker

```python
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
ec2 = boto3.client("ec2")


def launch_spot_worker(subnet_id: str, sg_id: str, ami_id: str) -> str:
    try:
        response = ec2.run_instances(
            InstanceMarketOptions={
                "MarketType": "spot",
                "SpotOptions": {"SpotInstanceType": "one-time"},
            },
            ImageId=ami_id,
            InstanceType="m5.xlarge",
            MinCount=1,
            MaxCount=1,
            SubnetId=subnet_id,
            SecurityGroupIds=[sg_id],
            IamInstanceProfile={"Name": "EC2ETLRole"},
            TagSpecifications=[{
                "ResourceType": "instance",
                "Tags": [{"Key": "Workload", "Value": "spark-etl"}],
            }],
        )
        instance_id = response["Instances"][0]["InstanceId"]
        logger.info("Launched spot instance %s", instance_id)
        return instance_id
    except ClientError:
        logger.exception("Failed to launch spot instance")
        raise
```

---

## Waiters

```python
ec2 = boto3.client("ec2")
waiter = ec2.get_waiter("instance_running")
waiter.wait(InstanceIds=["i-0abc123"])
```

---

## Best Practices

- Use **paginators** for `describe_instances` at scale.
- Handle **Spot interruption** with instance termination notices.
- Tag all resources at launch for cost tracking.
