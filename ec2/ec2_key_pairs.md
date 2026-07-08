# EC2 — Key Pairs

## Service Overview

EC2 key pairs provide SSH access to Linux instances. Prefer SSM Session Manager over SSH in production.

---

## AWS CLI Commands

### Create Key Pair

```bash
aws ec2 create-key-pair --key-name data-pipeline-key --query 'KeyMaterial' --output text > data-pipeline-key.pem
chmod 400 data-pipeline-key.pem
```

### List Key Pairs

```bash
aws ec2 describe-key-pairs --query 'KeyPairs[].KeyName' --output table
```

### Delete Key Pair

```bash
aws ec2 delete-key-pair --key-name old-key
```

### SSH Connect

```bash
ssh -i data-pipeline-key.pem ec2-user@10.0.1.50
```

---

## Python (Boto3) Examples

```python
import boto3

ec2 = boto3.client("ec2")
response = ec2.create_key_pair(KeyName="automation-key")
private_key = response["KeyMaterial"]
# Store securely — never log or commit
```

---

## Security Considerations

- Store private keys in **Secrets Manager** or secure vault — never in Git.
- Rotate keys periodically; use **SSM** for shell access instead.
- Restrict key usage to bastion hosts only.

---

## Best Practices

- Use **EC2 Instance Connect** or **SSM Session Manager** where possible.
- Disable password authentication on instances.
- Audit key pairs quarterly and delete unused keys.
