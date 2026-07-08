# VPC — Subnets & Route Tables

## Service Overview

Subnets segment VPC CIDR blocks by AZ. Route tables control traffic flow to internet gateway, NAT gateway, and VPC endpoints.

---

## AWS CLI Commands

### Create Route Table

```bash
aws ec2 create-route-table --vpc-id vpc-0abc123 \
  --tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=private-rt-1a}]'
```

### Associate Subnet with Route Table

```bash
aws ec2 associate-route-table \
  --route-table-id rtb-0abc123 \
  --subnet-id subnet-0def456
```

### Add NAT Gateway Route

```bash
aws ec2 create-route \
  --route-table-id rtb-0abc123 \
  --destination-cidr-block 0.0.0.0/0 \
  --nat-gateway-id nat-0def456
```

### List Route Tables

```bash
aws ec2 describe-route-tables \
  --filters Name=vpc-id,Values=vpc-0abc123 \
  --query 'RouteTables[].{ID:RouteTableId,Routes:Routes}' \
  --output json
```

---

## Best Practices

- One **private route table per AZ** for blast radius isolation.
- S3/DynamoDB traffic should route via **gateway endpoints**, not NAT.
- Tag route tables with `Tier=private|public`.
