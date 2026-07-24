# AWS Authentication for S3

This document exists because most production S3 incidents start with unclear
identity, unclear permissions, or unsafe credentials.

## What It Does

AWS authentication answers two questions:

- Who is calling the S3 API?
- What is that caller allowed to do?

boto3 resolves credentials through the AWS credential provider chain. Common
sources include environment variables, named profiles, container credentials,
EC2 instance profiles, web identity tokens, and SSO-backed profiles.

## When To Use Each Method

Use IAM roles for production workloads on AWS compute. Use named profiles for
local development. Use STS AssumeRole for cross-account access, break-glass
operations, and privilege separation. Use MFA when humans assume privileged
roles. Avoid IAM users unless an integration cannot support roles.

## Advantages

- Short-lived STS credentials reduce blast radius.
- Named profiles keep local workflows repeatable.
- Role assumption creates CloudTrail audit trails.
- MFA protects privileged human operations.

## Disadvantages

- Cross-account role chains can be hard to debug.
- MFA automation requires secure token handling.
- Environment variables are easy to leak through logs or shell history.
- Long-lived access keys require rotation and monitoring.

## AWS Limitations

STS credentials expire. Role chaining can reduce maximum session duration.
Some services and SDK integrations require region-aware sessions. S3 bucket
policies evaluate identity policies, resource policies, explicit denies, and
organization controls together.

## Pricing Considerations

STS calls are usually not the dominant cost. The real cost risk is accidental
access to large buckets, excessive listing, or high-volume data events after
credentials are granted.

## Security Considerations

Never commit credentials. Never log secret keys or session tokens. Always log
the account and ARN returned by `sts:GetCallerIdentity` before running risky
operations. Prefer least-privilege policies and explicit denies for mandatory
controls such as TLS and encryption.

## Performance Considerations

Credential resolution can add startup latency. Create sessions once and reuse
clients for related operations. Configure botocore connection pools and retry
settings for high-throughput tools.

## Production Recommendations

- Use `AwsSessionFactory` from `src/s3_learning/session.py`.
- Set `AWS_PROFILE` for local work.
- Set `AWS_REGION` explicitly.
- Validate caller identity before destructive actions.
- Prefer role-based access over static keys.

## Common Mistakes

- Assuming `AccessDenied` means a bucket does not exist.
- Mixing profiles and environment credentials accidentally.
- Forgetting MFA token parameters during role assumption.
- Giving S3 wildcard permissions for convenience.

## Interview Questions

- How does boto3 find credentials?
- Why are IAM roles preferred over IAM users?
- How does an S3 bucket policy interact with an IAM identity policy?
- What information should a tool log before deleting S3 objects?

