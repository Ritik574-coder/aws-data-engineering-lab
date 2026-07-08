# Troubleshooting — Networking Issues

## Service Overview

Networking problems prevent AWS CLI and Boto3 from reaching AWS service endpoints. Data engineering workloads in private subnets — Glue connections, EMR, EC2 ETL nodes, ECS tasks — commonly hit DNS, routing, security group, NACL, and VPC endpoint issues.

---

## AWS CLI Commands

### Test Basic Connectivity

```bash
# DNS resolution
dig +short s3.us-east-1.amazonaws.com
nslookup sts.us-east-1.amazonaws.com

# HTTPS connectivity
curl -v --connect-timeout 5 https://sts.us-east-1.amazonaws.com 2>&1 | head -30

# AWS API call (tests full path)
aws sts get-caller-identity
```

### Verify VPC and Subnet

```bash
aws ec2 describe-subnets --subnet-ids subnet-abc123 \
  --query 'Subnets[0].[VpcId,CidrBlock,AvailabilityZone,MapPublicIpOnLaunch]'

aws ec2 describe-route-tables \
  --filters "Name=association.subnet-id,Values=subnet-abc123" \
  --query 'RouteTables[0].Routes'
```

### Check Security Groups

```bash
aws ec2 describe-security-groups --group-ids sg-abc123 \
  --query 'SecurityGroups[0].[GroupName,IpPermissions,IpPermissionsEgress]'
```

### List VPC Endpoints

```bash
aws ec2 describe-vpc-endpoints \
  --filters "Name=vpc-id,Values=vpc-abc123" \
  --query 'VpcEndpoints[*].[ServiceName,State,VpcEndpointType]' \
  --output table
```

### Test S3 via Gateway Endpoint

```bash
# From instance in VPC with S3 gateway endpoint
aws s3 ls s3://my-data-lake-raw/ --region us-east-1
traceroute s3.us-east-1.amazonaws.com 2>&1 | head -10
```

---

## Advanced Commands

### Create Interface VPC Endpoint (Private AWS API Access)

```bash
aws ec2 create-vpc-endpoint \
  --vpc-id vpc-abc123 \
  --service-name com.amazonaws.us-east-1.glue \
  --vpc-endpoint-type Interface \
  --subnet-ids subnet-private-a subnet-private-b \
  --security-group-ids sg-endpoint \
  --private-dns-enabled
```

### NAT Gateway Route Check

Private subnet route table should have:

```bash
aws ec2 describe-route-tables \
  --route-table-ids rtb-private \
  --query 'RouteTables[0].Routes[?DestinationCidrBlock==`0.0.0.0/0`]'
```

Expected: `NatGatewayId` for private subnets needing internet access.

### DNS Resolution in VPC

```bash
aws ec2 describe-vpc-attribute --vpc-id vpc-abc123 --attribute enableDnsSupport
aws ec2 describe-vpc-attribute --vpc-id vpc-abc123 --attribute enableDnsHostnames
```

Both must be `true` for private DNS on interface endpoints.

### VPC Endpoint Policy (S3)

```bash
aws ec2 describe-vpc-endpoints --vpc-endpoint-ids vpce-abc123 \
  --query 'VpcEndpoints[0].PolicyDocument' --output text | python3 -m json.tool
```

### Network ACL Check

```bash
aws ec2 describe-network-acls \
  --filters "Name=association.subnet-id,Values=subnet-abc123" \
  --query 'NetworkAcls[0].Entries'
```

---

## Python Boto3 Examples

### Diagnose Connection Error

```python
import boto3
from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError

try:
    boto3.client("s3").list_buckets()
except EndpointConnectionError as exc:
    print(f"Cannot reach endpoint: {exc}")
except ClientError as exc:
    print(f"AWS error: {exc.response['Error']['Code']}")
except BotoCoreError as exc:
    print(f"Network error: {exc}")
```

### Custom Endpoint (LocalStack / VPC Endpoint)

```python
import boto3

s3 = boto3.client(
    "s3",
    endpoint_url="https://s3.us-east-1.amazonaws.com",
    region_name="us-east-1",
)

# PrivateLink-specific endpoint
glue = boto3.client(
    "glue",
    endpoint_url="https://vpce-abc123-glue.us-east-1.vpce.amazonaws.com",
    region_name="us-east-1",
)
```

---

## Security Considerations

- Restrict security groups on interface endpoints to required CIDRs only.
- VPC endpoint policies can deny access — treat them like IAM policies in troubleshooting.
- Avoid open `0.0.0.0/0` egress except through controlled NAT for package updates.

---

## Troubleshooting

| Symptom | Root Cause | Resolution |
|---------|------------|------------|
| `Could not connect to the endpoint URL` | No route to AWS | Add NAT gateway or VPC endpoint |
| `Connection timed out` | SG/NACL blocks HTTPS | Allow egress TCP 443; check NACL inbound return traffic |
| `Name or service not known` | DNS failure | Enable VPC DNS; check Route 53 resolver |
| Works on EC2 public, fails private | Missing NAT or endpoint | Add gateway endpoint (S3/DynamoDB) or interface endpoint |
| S3 works, Glue fails | Missing Glue endpoint | Create interface endpoint for Glue |
| Intermittent timeouts | NAT gateway capacity | Scale NAT; split AZ traffic; use endpoints |
| `AccessDenied` via endpoint only | Endpoint policy deny | Update VPC endpoint policy document |
| IMDS timeout on EC2 | IMDSv2 hop limit in containers | Set `HttpPutResponseHopLimit=2` for ECS |
| Proxy errors | Corporate proxy misconfigured | Set `HTTP_PROXY`/`HTTPS_PROXY`; configure `NO_PROXY` for VPC CIDR |

### Architecture Reference

```
Private Subnet (ETL)
├── S3/DynamoDB → Gateway Endpoint (free, route table entry)
├── Glue, STS, KMS → Interface Endpoint (PrivateLink, per-AZ ENI)
├── Internet (PyPI, external APIs) → NAT Gateway → IGW
└── On-prem → VPN/Direct Connect → Transit Gateway
```

### Security Group Minimum for Interface Endpoints

| Direction | Protocol | Port | Source |
|-----------|----------|------|--------|
| Inbound | TCP | 443 | VPC CIDR or client SG |
| Outbound | TCP | 443 | 0.0.0.0/0 (return traffic) |

---

## Best Practices

- Use **VPC endpoints** for S3, Glue, Athena, STS, KMS in private subnets — reduce NAT costs and improve security.
- Enable **`private-dns-enabled`** on interface endpoints for transparent SDK usage.
- Place endpoints in **multiple AZs** for high availability.
- Monitor **NAT gateway** `BytesOutToDestination` — high usage signals missing endpoints.
- Document **required endpoints** per pipeline in network architecture diagrams.
- Test connectivity from the **same subnet/SG** as production workloads — not your laptop.
- Use **Network Firewall** or **SG rules** for egress filtering in regulated environments.
