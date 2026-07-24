"""Production Amazon S3 learning package.

This package contains reusable, typed boto3 examples that teach Amazon S3
through production-quality Python modules. The code favors explicit clients,
structured configuration, defensive error handling, pagination, waiters, and
clear logging so the examples can be adapted to real engineering work.
"""

from s3_learning.config import AppConfig
from s3_learning.session import AwsSessionFactory

__all__ = ["AppConfig", "AwsSessionFactory"]

