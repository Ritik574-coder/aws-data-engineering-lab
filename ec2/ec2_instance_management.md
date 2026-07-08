# EC2 — Instance Management

## Service Overview

**Amazon EC2** provides resizable compute capacity. Data engineers use EC2 for self-managed Spark clusters, Airflow workers, bastion hosts, and custom ETL runners.

---

## AWS CLI Commands

### Launch Instance

```bash
aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type m5.xlarge \
  --key-name data-pipeline-key \
  --subnet-id subnet-0abc123 \
  --security-group-ids sg-0def456 \
  --iam-instance-profile Name=EC2ETLRole \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=etl-worker-01},{Key=Team,Value=DataEng}]' \
  --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":100,"VolumeType":"gp3","Encrypted":true}}]'
```

### List Instances

```bash
aws ec2 describe-instances \
  --filters "Name=tag:Team,Values=DataEng" "Name=instance-state-name,Values=running" \
  --query 'Reservations[].Instances[].{ID:InstanceId,Type:InstanceType,IP:PrivateIpAddress,State:State.Name}' \
  --output table
```

### Stop / Start Instance

```bash
aws ec2 stop-instances --instance-ids i-0abc123def456
aws ec2 start-instances --instance-ids i-0abc123def456
```

### Terminate Instance

```bash
aws ec2 terminate-instances --instance-ids i-0abc123def456
```

---

## Advanced Commands

### Get Instance Metadata (from within instance)

```bash
TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
curl -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/iam/security-credentials/
```

### Modify Instance Type

```bash
aws ec2 modify-instance-attribute \
  --instance-id i-0abc123def456 \
  --instance-type "{\"Value\": \"m5.2xlarge\"}"
```

---

## Python (Boto3) Examples

```python
import boto3

ec2 = boto3.client("ec2")

def stop_instances_by_tag(tag_key: str, tag_value: str) -> list[str]:
    response = ec2.describe_instances(
        Filters=[
            {"Name": f"tag:{tag_key}", "Values": [tag_value]},
            {"Name": "instance-state-name", "Values": ["running"]},
        ]
    )
    ids = [
        i["InstanceId"]
        for r in response["Reservations"]
        for i in r["Instances"]
    ]
    if ids:
        ec2.stop_instances(InstanceIds=ids)
    return ids
```

---

## Security Considerations

- Use **IAM instance profiles** instead of embedding credentials.
- Place ETL workers in **private subnets**; use SSM Session Manager instead of SSH.
- Encrypt EBS volumes by default; use **IMDSv2** (`HttpTokens=required`).

---

## Troubleshooting

| Error | Root Cause | Resolution |
|-------|------------|------------|
| `InsufficientInstanceCapacity` | AZ capacity exhausted | Retry different AZ or instance type |
| `UnauthorizedOperation` | Missing ec2:RunInstances | Update IAM policy |

---

## Best Practices

- Use **Auto Scaling Groups** for worker fleets.
- Right-size with **CloudWatch metrics** (CPU, memory via agent).
- Use **Spot Instances** for fault-tolerant batch workloads.
- Tag instances for cost allocation and automation.
