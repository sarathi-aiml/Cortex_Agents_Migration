# Cortex Agents DDL Generator - Python Script

## Overview

`cortex_agents_ddl.py` is a Python command-line tool that generates SQL `CREATE AGENT` statements from existing Snowflake Cortex Agents. It connects to your Snowflake account, retrieves agent specifications, and outputs the DDL statements that can be used to recreate or migrate agents.

## Features

- ✅ Generates complete SQL CREATE AGENT statements
- ✅ Reads credentials from environment file (env.dev)
- ✅ Supports Personal Access Token (PAT) authentication
- ✅ Command-line interface for easy automation
- ✅ Identical SQL generation logic as the stored procedure version
- ✅ Handles all agent components: models, instructions, tools, tool_resources, orchestration, profile

## Prerequisites

1. **Python 3.10 or higher**
2. **Access to Snowflake account** with:
   - Valid Personal Access Token (PAT)
   - Permissions to DESCRIBE agents in the target database/schema
3. **Network access** to your Snowflake account

## Installation

### Step 1: Install Python Dependencies

```bash
# Using pip
pip install -r requirement_cortex_agents_ddl.txt

# Or install manually
pip install snowflake-snowpark-python>=1.0.0 python-dotenv>=1.0.0
```

### Step 2: Configure Environment File

Create or edit `env.dev` file in the same directory as the script with the following variables:

```properties
# Required: Snowflake Account Configuration
SOURCE_ACCOUNT_URL=https://<ACCOUNT_IDENTIFIER>.snowflakecomputing.com
SOURCE_USER=<your_username>
SOURCE_PAT=<your_personal_access_token>
SOURCE_WAREHOUSE=<your_warehouse_name>
SOURCE_DATABASE=<your_database_name>
SOURCE_SCHEMA=<your_schema_name>
```

#### Example `env.dev` file:

```properties
SOURCE_ACCOUNT_URL=https://<YOUR_ACCOUNT_IDENTIFIER>.snowflakecomputing.com
SOURCE_USER=<YOUR_USERNAME>
SOURCE_PAT=<YOUR_PERSONAL_ACCESS_TOKEN>
SOURCE_WAREHOUSE=<YOUR_WAREHOUSE_NAME>
SOURCE_DATABASE=<YOUR_DATABASE_NAME>
SOURCE_SCHEMA=<YOUR_SCHEMA_NAME>
```

#### Getting Your Account URL:

Your account URL format is: `https://<ACCOUNT_IDENTIFIER>.snowflakecomputing.com`

You can find your account identifier:
- In your Snowflake web UI URL
- In your connection strings
- From your Snowflake administrator

#### Creating a Personal Access Token (PAT):

1. Log in to Snowflake web UI
2. Navigate to **Admin** → **Users & Security** → **Personal Access Tokens**
3. Click **Generate Token**
4. Provide a name and expiration date
5. Copy the generated token (you'll only see it once)
6. Paste it in `env.dev` as `SOURCE_PAT`

⚠️ **Important**: Keep your PAT secure and never commit it to version control!

## Usage

### Basic Syntax

```bash
python cortex_agents_ddl.py --database <DATABASE> --schema <SCHEMA> --agent <AGENT_NAME>
```

### Command-Line Arguments

| Argument | Short Form | Required | Description |
|----------|-----------|----------|-------------|
| `--database` | `-d` | Yes | Name of the database containing the agent |
| `--schema` | `-s` | Yes | Name of the schema containing the agent |
| `--agent` | `-a` | Yes | Name of the agent to generate DDL for |
| `--env-file` | | No | Path to environment file (default: `env.dev`) |

### Examples

#### Example 1: Generate DDL for a Single Agent

```bash
python cortex_agents_ddl.py \
  --database SALES_INTELLIGENCE \
  --schema DATA \
  --agent SALES_INTELLIGENCE_AGENT
```

#### Example 2: Using Short Arguments

```bash
python cortex_agents_ddl.py -d SALES_INTELLIGENCE -s DATA -a SALES_INTELLIGENCE_AGENT
```

#### Example 3: Using Custom Environment File

```bash
python cortex_agents_ddl.py \
  --database SALES_INTELLIGENCE \
  --schema DATA \
  --agent SALES_INTELLIGENCE_AGENT \
  --env-file /path/to/my_env.dev
```

#### Example 4: Save Output to File

```bash
python cortex_agents_ddl.py -d SALES_INTELLIGENCE -s DATA -a SALES_INTELLIGENCE_AGENT > agent_ddl.sql
```

#### Example 5: Using in Scripts/Automation

```bash
#!/bin/bash
DATABASE="SALES_INTELLIGENCE"
SCHEMA="DATA"
AGENT="SALES_INTELLIGENCE_AGENT"

python cortex_agents_ddl.py -d "$DATABASE" -s "$SCHEMA" -a "$AGENT" > "${AGENT}_ddl.sql"
```

### Output

The script outputs a complete SQL `CREATE OR REPLACE AGENT` statement to stdout. Example output:

```sql
CREATE OR REPLACE AGENT SALES_INTELLIGENCE.DATA.SALES_INTELLIGENCE_AGENT
COMMENT = 'Sales Intelligence Agent with multiple tools'
FROM SPECIFICATION
$$
models:
  orchestration: "claude-4-sonnet"

instructions:
  response: "Provide detailed, data-driven insights..."
  orchestration: "Use the Cortex Analyst tool..."
  sample_questions:
    - question: "What are our top performing products?"

tools:
  - tool_spec:
      type: "cortex_analyst_text_to_sql"
      name: "SalesAnalyst"
      description: "Analyze sales data using SQL queries"
  ...

tool_resources:
  SalesAnalyst:
    execution_environment:
      type: "warehouse"
      warehouse: "SB_DW_XS"
    semantic_model_file: "@SALES_INTELLIGENCE.DATA.MODELS/sales_metrics_model.yaml"
  ...

$$;
```

## Troubleshooting

### Common Errors

#### Error: `SOURCE_USER not found in env.dev`
**Solution**: Ensure your `env.dev` file contains `SOURCE_USER=<your_username>`

#### Error: `SOURCE_PAT not found in env.dev`
**Solution**: Ensure your `env.dev` file contains `SOURCE_PAT=<your_token>`

#### Error: `Invalid account URL format`
**Solution**: Check that `SOURCE_ACCOUNT_URL` follows the format: `https://<ACCOUNT>.snowflakecomputing.com`

#### Error: `Failed to connect to DB: Invalid OAuth access token`
**Possible causes:**
- PAT token has expired
- PAT token is incorrect
- Account URL is incorrect
- Network connectivity issues

**Solution**:
- Generate a new PAT token
- Verify the token in `env.dev` is correct (no extra spaces)
- Verify account URL is correct
- Check network/firewall settings

#### Error: `Agent not found or DESCRIBE failed`
**Possible causes:**
- Agent name is misspelled
- Agent doesn't exist in the specified database/schema
- Insufficient permissions to DESCRIBE the agent

**Solution**:
- Verify agent name, database, and schema are correct
- Check that you have DESCRIBE permissions on the agent
- List agents using: `SHOW AGENTS IN SCHEMA <database>.<schema>`

#### Error: `ModuleNotFoundError: No module named 'snowflake'`
**Solution**: Install dependencies:
```bash
pip install -r requirement_cortex_agents_ddl.txt
```

#### Error: `ModuleNotFoundError: No module named 'dotenv'`
**Solution**: Install python-dotenv:
```bash
pip install python-dotenv
```

### Debugging Tips

1. **Test environment file loading:**
   ```bash
   python -c "from dotenv import load_dotenv; import os; load_dotenv('env.dev'); print(os.getenv('SOURCE_USER'))"
   ```

2. **Test connection separately:**
   ```python
   from cortex_agents_ddl import create_session_from_env
   session = create_session_from_env('env.dev')
   print("Connection successful!")
   ```

3. **Verify agent exists:**
   ```sql
   SHOW AGENTS IN SCHEMA <database>.<schema>;
   DESCRIBE AGENT <database>.<schema>.<agent_name>;
   ```

## Advanced Usage

### Using with Conda Environment

```bash
conda activate py311
python cortex_agents_ddl.py -d SALES_INTELLIGENCE -s DATA -a SALES_INTELLIGENCE_AGENT
```

### Batch Processing Multiple Agents

```bash
#!/bin/bash
AGENTS=(
  "AGENT1"
  "AGENT2"
  "AGENT3"
)

for agent in "${AGENTS[@]}"; do
  python cortex_agents_ddl.py -d SALES_INTELLIGENCE -s DATA -a "$agent" > "${agent}_ddl.sql"
done
```

### Integration with CI/CD

```yaml
# Example GitHub Actions workflow
- name: Generate Agent DDL
  env:
    SOURCE_PAT: ${{ secrets.SNOWFLAKE_PAT }}
    SOURCE_USER: ${{ secrets.SNOWFLAKE_USER }}
    SOURCE_ACCOUNT_URL: ${{ secrets.SNOWFLAKE_ACCOUNT_URL }}
  run: |
    python cortex_agents_ddl.py -d $DATABASE -s $SCHEMA -a $AGENT > agent_ddl.sql
```

## Output Format

The generated SQL follows Snowflake's CREATE AGENT syntax:
- Preserves all agent configuration
- Includes models, instructions, tools, tool_resources
- Maintains proper YAML formatting in the specification
- Handles long descriptions with truncation
- Preserves field ordering based on tool type

## Security Best Practices

1. **Never commit `env.dev` to version control**
   - Add `env.dev` to `.gitignore`
   - Use environment variables or secrets management in CI/CD

2. **Use minimal required permissions**
   - PAT token should only have permissions to DESCRIBE agents
   - Consider using role-based access control

3. **Rotate PAT tokens regularly**
   - Set expiration dates on tokens
   - Monitor token usage

4. **Secure file permissions**
   ```bash
   chmod 600 env.dev  # Restrict read/write to owner only
   ```

## Related Tools

- `generate_agent_sql_procedure.sql` - Snowflake stored procedure version
- `SiS_Version.py` - Streamlit-in-Snowflake web interface version

## Support

For issues or questions:
1. Check the troubleshooting section
2. Verify your environment file configuration
3. Test with a simple agent first
4. Review Snowflake documentation for agent permissions

## License

This script is part of the Snowflake Cortex Agent Migration toolkit.

