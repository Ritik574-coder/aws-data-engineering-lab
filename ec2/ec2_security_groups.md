# EC2 — Security Groups

## Service Overview

Security groups act as virtual firewalls for EC2 instances, controlling inbound and outbound traffic at the ENI level.

---

## AWS CLI Commands

### Create Security Group

```bash
aws ec2 create-security-group \
  --group-name etl-workers-sg \
  --description "Security group for ETL worker instances" \
  --vpc-id vpc-0abc123
```

### Add Inbound Rule

```bash
aws ec2 authorize-security-group-ingress \
  --group-id sg-0def456 \
  --protocol tcp \
  --port 22 \
  --cidr 10.0.0.0/8
```

### Add Outbound Rule (HTTPS for AWS APIs)

```bash
aws ec2 authorize-security-group-egress \
  --group-id sg-0def456 \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0
```

### Describe Security Groups

```bash
aws ec2 describe-security-groups \
  --group-ids sg-0def456 \
  --query 'SecurityGroups[0].{Name:GroupName,Inbound:IpPermissions,Outbound:IpPermissionsEgress}'
```

---

## Advanced Commands

### Reference Another SG (Peer Access)

```bash
aws ec2 authorize-security-group-ingress \
  --group-id sg-worker \
  --protocol tcp \
  --port 8080 \
  --source-group sg-bastion
```

---

## Python (Boto3) Examples

```python
import boto3

ec2 = boto3.client("ec2")

def allow_https_egress(group_id: str) -> None:
    ec2.authorize_security_group_egress(
        GroupId=group_id,
        IpPermissions=[{
            "IpProtocol": "tcp",
            "FromPort": 443,
            "ToPort": 443,
            "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "AWS API access"}],
        }],
    )
```

---

## Security Considerations

- **Deny SSH from 0.0.0.0/0** — use SSM Session Manager or bastion in private subnet.
- Restrict egress to required endpoints (S3 VPC endpoint, Glue, etc.).
- Review rules with **VPC Reachability Analyzer**.

---

## Best Practices

- One SG per **application tier** (workers, bastion, load balancer).
- Document rule purpose in `Description` field.
- Use **prefix lists** for AWS service IP ranges where applicable.
