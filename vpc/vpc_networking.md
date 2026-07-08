# VPC — Networking

## Service Overview

**Amazon VPC** provides isolated network environments. Data platforms typically use private subnets for compute, VPC endpoints for AWS services, and NAT for controlled outbound access.

**Common use cases:**
- Private subnets for Glue connections, EMR, RDS
- S3/Glue/Athena VPC endpoints (avoid NAT costs)
- Peering or Transit Gateway for multi-VPC data mesh

---

## AWS CLI Commands

### Create VPC

```bash
aws ec2 create-vpc --cidr-block 10.0.0.0/16 \
  --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=data-platform-vpc}]'
```

### Create Subnet

```bash
aws ec2 create-subnet \
  --vpc-id vpc-0abc123 \
  --cidr-block 10.0.1.0/24 \
  --availability-zone us-east-1a \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=private-etl-1a}]'
```

### Create S3 Gateway Endpoint

```bash
aws ec2 create-vpc-endpoint \
  --vpc-id vpc-0abc123 \
  --service-name com.amazonaws.us-east-1.s3 \
  --route-table-ids rtb-0def456
```

### Create Interface Endpoint (Glue)

```bash
aws ec2 create-vpc-endpoint \
  --vpc-id vpc-0abc123 \
  --vpc-endpoint-type Interface \
  --service-name com.amazonaws.us-east-1.glue \
  --subnet-ids subnet-0abc123 \
  --security-group-ids sg-0def456
```

### Describe VPCs

```bash
aws ec2 describe-vpcs \
  --query 'Vpcs[].{ID:VpcId,CIDR:CidrBlock,Name:Tags[?Key==`Name`].Value|[0]}' \
  --output table
```

---

## Advanced Commands

### VPC Peering

```bash
aws ec2 create-vpc-peering-connection \
  --vpc-id vpc-source \
  --peer-vpc-id vpc-target \
  --peer-region us-west-2
```

### Flow Logs

```bash
aws ec2 create-flow-logs \
  --resource-type VPC \
  --resource-ids vpc-0abc123 \
  --traffic-type ALL \
  --log-destination-type cloud-watch-logs \
  --log-group-name /vpc/flowlogs/data-platform
```

---

## Python (Boto3) Examples

```python
import boto3

ec2 = boto3.client("ec2")

def get_private_subnets(vpc_id: str) -> list[str]:
    subnets = ec2.describe_subnets(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
    )["Subnets"]
    return [s["SubnetId"] for s in subnets if s.get("MapPublicIpOnLaunch") is False]
```

---

## Security Considerations

- Place data services in **private subnets** without public IPs.
- Use **NACLs** as stateless defense; SGs as primary control.
- Enable **VPC Flow Logs** for anomaly detection.

---

## Troubleshooting

| Issue | Root Cause | Resolution |
|-------|------------|------------|
| Cannot reach S3 from private subnet | Missing gateway endpoint | Add S3 VPC endpoint to route table |
| Glue job network timeout | Missing interface endpoint or NAT | Add Glue interface endpoint |
| DNS resolution fails | enableDnsSupport disabled | Enable DNS support/hostnames on VPC |

---

## Best Practices

- **Three-tier subnet design**: public (NAT/LB), private (compute), isolated (data stores).
- Use **VPC endpoints** for S3, DynamoDB, Glue, Athena, STS, KMS.
- Document CIDR allocation to avoid overlapping peering CIDRs.
