# AWS Lambda Agent Setup Guide

These are instructions from AWS to set up AI agent integrations for building and deploying serverless applications on AWS Lambda. All commands are validated and ready to use.

---

## Validate authentication with AWS

Check whether the user has valid AWS credentials by running:

```bash
aws sts get-caller-identity
```

If the command succeeds and shows the user Account and Arn, the user is authenticated. If it fails (missing, expired, or invalid credentials), fetch and follow the signing-in-to-aws skill:

https://github.com/aws/agent-toolkit-for-aws/blob/main/skills/core-skills/signing-in-to-aws/SKILL.md

---

## Install the AWS serverless skill

Use the correct section for your agent below.

### Claude Code 

#### Install the aws-core plugin from Agent Toolkit for AWS

Run these commands to install the AWS serverless skill, agent hooks, and the AWS MCP Server configuration in one step.
```
claude plugin marketplace add aws/agent-toolkit-for-aws
claude plugin install aws-core@agent-toolkit-for-aws
```

### Install for other agents such as Cursor, Kiro CLI, GitHub Copilot, Codex, Devin Desktop, and OpenCode
```bash
npx skills add https://github.com/aws/agent-toolkit-for-aws --skill aws-serverless --yes --global
```
---
## Install additional AWS Lambda skills using any agent such as Claude Code, Cursor, Kiro CLI, GitHub Copilot, Codex, Devin Desktop, and OpenCode

Install Lambda MicroVM skill:
```bash
npx skills add https://github.com/aws/agent-toolkit-for-aws/tree/main/skills/specialized-skills/serverless-skills/aws-lambda-microvms --yes --global
```

Install Lambda Managed Instances skill: 
```bash 
npx skills add https://github.com/aws/agent-toolkit-for-aws/tree/main/skills/specialized-skills/serverless-skills/aws-lambda-managed-instances --yes --global
```

Install Lambda durable functions skill: 
```bash 
npx skills add https://github.com/aws/agent-toolkit-for-aws/tree/main/skills/specialized-skills/serverless-skills/aws-lambda-durable-functions --yes --global
```
---

## AWS Serverless MCP Server

Register the Serverless MCP Server based on your agent. Replace `AWS_PROFILE` with your local AWS profile name.

### Kiro

Config file: `~/.kiro/settings/mcp.json`

Add under `"mcpServers"`:

```json
"awslabs.aws-serverless-mcp": {
  "command": "uvx",
  "args": ["awslabs.aws-serverless-mcp-server@latest"],
  "env": {
    "AWS_PROFILE": <your profile here>,
    "AWS_REGION": "us-east-1",
    "FASTMCP_LOG_LEVEL": "ERROR"
  },
  "disabled": false
}
```

### Claude Code

```bash
claude mcp add awslabs-aws-serverless-mcp \
  -e AWS_PROFILE=<your profile here> \
  -e AWS_REGION=us-east-1 \
  -e FASTMCP_LOG_LEVEL=ERROR \
  --scope user \
  -- uvx awslabs.aws-serverless-mcp-server@latest
```

### Codex

```bash
codex mcp add awslabs-aws-serverless-mcp \
  --env AWS_PROFILE=<your profile here> \
  --env AWS_REGION=us-east-1 \
  --env FASTMCP_LOG_LEVEL=ERROR \
  -- uvx awslabs.aws-serverless-mcp-server@latest
```

### Cursor, GitHub Copilot, Devin Desktop, OpenCode, and all other agents

Add to your agent's MCP config file under `"mcpServers"`:

| Agent | Config file |
|-------|-------------|
| Cursor | `.cursor/mcp.json` |
| GitHub Copilot | `.vscode/mcp.json` |
| Devin Desktop | `~/.codeium/windsurf/mcp_config.json` |
| OpenCode | `~/.config/opencode/opencode.jsonc` |

```json
"awslabs.aws-serverless-mcp": {
  "command": "uvx",
  "args": ["awslabs.aws-serverless-mcp-server@latest"],
  "env": {
    "AWS_PROFILE": <your profile here>,
    "AWS_REGION": "us-east-1",
    "FASTMCP_LOG_LEVEL": "ERROR"
  }
}
```