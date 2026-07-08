# VPC — Python Boto3 Examples

## Examples

```python
import boto3

ec2 = boto3.client("ec2")

def ensure_s3_endpoint(vpc_id: str, route_table_id: str, region: str) -> str:
    service = f"com.amazonaws.{region}.s3"
    response = ec2.create_vpc_endpoint(
        VpcId=vpc_id,
        ServiceName=service,
        RouteTableIds=[route_table_id],
    )
    return response["VpcEndpoint"]["VpcEndpointId"]
```

---

## Best Practices

- Check for existing endpoints before creating duplicates.
- Use **waiters** when provisioning NAT gateways for route updates.
