# Generate Agent SQL Stored Procedure

## Overview

`generate_agent_sql_procedure.sql` is a Snowflake stored procedure that generates SQL `CREATE AGENT` statements from existing Cortex Agents. It runs entirely within Snowflake, eliminating the need for external tools or authentication setup.

## Features

- ✅ Runs natively in Snowflake (no external dependencies)
- ✅ Generates complete SQL CREATE AGENT statements
- ✅ Identical SQL generation logic as the Python script version
- ✅ Handles all agent components: models, instructions, tools, tool_resources, orchestration, profile
- ✅ Can be called from SQL scripts or Snowflake worksheets
- ✅ Returns SQL as a string that can be executed or saved

## Prerequisites

1. **Snowflake Account** with:
   - Access to the database/schema containing agents
   - Permissions to:
     - CREATE PROCEDURE (to deploy the stored procedure)
     - DESCRIBE agents in target databases/schemas
     - EXECUTE the stored procedure

2. **Python Runtime** (handled automatically by Snowflake)
   - Uses Snowflake's built-in Python runtime (3.10)
   - No additional installation required

## Installation

### Step 1: Set Your Database and Schema Context

Before creating the stored procedure, set your working context:

```sql
USE DATABASE <YOUR_DATABASE>;
USE SCHEMA <YOUR_SCHEMA>;
```

Replace `<YOUR_DATABASE>` and `<YOUR_SCHEMA>` with your target database and schema where you want to create the procedure.

**Example:**
```sql
USE DATABASE UTILITY_DB;
USE SCHEMA AGENT_TOOLS;
```

### Step 2: Create the Stored Procedure

Open `generate_agent_sql_procedure.sql` in Snowflake worksheets or your SQL editor, ensure the USE commands are set correctly, and execute the entire script.

**Option A: Using Snowflake Worksheets**

1. Log in to Snowflake web UI
2. Navigate to **Worksheets**
3. Open `generate_agent_sql_procedure.sql`
4. Update the USE commands at the top (or manually set context)
5. Select all and execute (Ctrl+A, then click Run)

**Option B: Using SnowSQL/CLI**

```bash
snowsql -f generate_agent_sql_procedure.sql
```

**Option C: Using Python/Snowpark**

```python
from snowflake.snowpark import Session

session = Session.builder.configs({
    "account": "<account>",
    "user": "<user>",
    "password": "<password>",
    "warehouse": "<warehouse>",
    "database": "<database>",
    "schema": "<schema>"
}).create()

# Read and execute the SQL file
with open('generate_agent_sql_procedure.sql', 'r') as f:
    sql = f.read()
    
session.sql(sql).collect()
```

### Step 3: Verify Installation

Verify the procedure was created successfully:

```sql
SHOW PROCEDURES LIKE 'GENERATE_AGENT_SQL';
DESCRIBE PROCEDURE GENERATE_AGENT_SQL(STRING, STRING, STRING);
```

## Usage

### Basic Syntax

```sql
CALL GENERATE_AGENT_SQL(
    '<DATABASE>',
    '<SCHEMA>',
    '<AGENT_NAME>'
);
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `DB` | STRING | Yes | Name of the database containing the agent |
| `SCH` | STRING | Yes | Name of the schema containing the agent |
| `AGENT_NAME` | STRING | Yes | Name of the agent to generate DDL for |

### Examples

#### Example 1: Generate DDL for a Single Agent

```sql
-- Set context
USE DATABASE UTILITY_DB;
USE SCHEMA AGENT_TOOLS;

-- Generate SQL
CALL GENERATE_AGENT_SQL(
    'SALES_INTELLIGENCE',
    'DATA',
    'SALES_INTELLIGENCE_AGENT'
);
```

#### Example 2: Save Output to a Table

```sql
-- Create a table to store results
CREATE OR REPLACE TABLE agent_ddl_history (
    agent_name STRING,
    database_name STRING,
    schema_name STRING,
    ddl_statement STRING,
    generated_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Generate and store DDL
-- First, call the procedure
CALL GENERATE_AGENT_SQL('SALES_INTELLIGENCE', 'DATA', 'SALES_INTELLIGENCE_AGENT');

-- Get the result and insert into table
INSERT INTO agent_ddl_history (agent_name, database_name, schema_name, ddl_statement)
SELECT 
    'SALES_INTELLIGENCE_AGENT' AS agent_name,
    'SALES_INTELLIGENCE' AS database_name,
    'DATA' AS schema_name,
    $1 AS ddl_statement
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
```

#### Example 3: Generate DDL for Multiple Agents

```sql
-- First, get list of agents using SHOW command
SHOW AGENTS IN SCHEMA SALES_INTELLIGENCE.DATA;

-- Then call the procedure for each agent individually:
CALL GENERATE_AGENT_SQL('SALES_INTELLIGENCE', 'DATA', 'AGENT1');
-- Get result: SELECT $1 AS ddl_statement FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));

CALL GENERATE_AGENT_SQL('SALES_INTELLIGENCE', 'DATA', 'AGENT2');
-- Get result: SELECT $1 AS ddl_statement FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));

CALL GENERATE_AGENT_SQL('SALES_INTELLIGENCE', 'DATA', 'AGENT3');
-- Get result: SELECT $1 AS ddl_statement FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));

-- Alternatively, create a procedure to loop through agents:
-- Note: You'll need to populate agent names manually or use a table
CREATE OR REPLACE TEMP TABLE agents_to_migrate AS
SELECT 'SALES_INTELLIGENCE' AS db, 'DATA' AS sch, 'AGENT1' AS agent_name
UNION ALL
SELECT 'SALES_INTELLIGENCE', 'DATA', 'AGENT2'
UNION ALL
SELECT 'SALES_INTELLIGENCE', 'DATA', 'AGENT3';

-- For batch processing, you'll need to call the procedure for each row manually
-- or create a Python stored procedure that can loop through the table
```

#### Example 4: Export to File (Using RESULT_SCAN)

```sql
-- Generate DDL
CALL GENERATE_AGENT_SQL('SALES_INTELLIGENCE', 'DATA', 'SALES_INTELLIGENCE_AGENT');

-- Get the result from the last query
SELECT $1 AS ddl_statement
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
```

#### Example 5: Create a Helper Procedure for Easy Access

```sql
-- Note: You cannot use stored procedures in views
-- Instead, create a helper procedure that takes agent name as parameter:

CREATE OR REPLACE PROCEDURE get_agent_ddl(
    target_database STRING,
    target_schema STRING,
    agent_name STRING
)
RETURNS STRING
LANGUAGE SQL
AS
$$
DECLARE
    ddl_result STRING;
BEGIN
    -- Call the GENERATE_AGENT_SQL procedure
    CALL GENERATE_AGENT_SQL(target_database, target_schema, agent_name);
    
    -- Get the result from the last query
    SELECT $1 INTO ddl_result
    FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
    
    RETURN ddl_result;
END;
$$;

-- Use the helper procedure
CALL get_agent_ddl('SALES_INTELLIGENCE', 'DATA', 'SALES_INTELLIGENCE_AGENT');

-- Or to list agents first and then get DDL for each:
SHOW AGENTS IN SCHEMA SALES_INTELLIGENCE.DATA;
-- Then call get_agent_ddl for each agent name you need
```

#### Example 6: Batch Processing Multiple Agents

```sql
-- First, list all agents in the schema
SHOW AGENTS IN SCHEMA SALES_INTELLIGENCE.DATA;

-- For batch processing, you need to manually call the procedure for each agent
-- or create a Python stored procedure that can iterate

-- Example: Create a table to store agent names (populated manually from SHOW AGENTS)
CREATE OR REPLACE TEMP TABLE agent_list AS
SELECT 'SALES_INTELLIGENCE' AS db, 'DATA' AS sch, 'AGENT1' AS agent_name
UNION ALL
SELECT 'SALES_INTELLIGENCE', 'DATA', 'AGENT2'
UNION ALL
SELECT 'SALES_INTELLIGENCE', 'DATA', 'AGENT3';

-- For each agent, call the procedure and save results
-- This would need to be done manually or via a Python stored procedure with a loop
-- Example manual approach:
CALL GENERATE_AGENT_SQL('SALES_INTELLIGENCE', 'DATA', 'AGENT1');

-- To automate, create a Python stored procedure:
CREATE OR REPLACE PROCEDURE generate_all_agent_ddl(
    target_database STRING,
    target_schema STRING
)
RETURNS TABLE(agent_name STRING, ddl_statement STRING)
LANGUAGE PYTHON
RUNTIME_VERSION = '3.10'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'generate_all_ddl'
AS
$$
def generate_all_ddl(session, target_database, target_schema):
    # Get list of agents
    agents = session.sql(f"SHOW AGENTS IN SCHEMA {target_database}.{target_schema}").collect()
    
    results = []
    for agent in agents:
        agent_name = agent['name']
        # Call the stored procedure
        ddl = session.call('GENERATE_AGENT_SQL', target_database, target_schema, agent_name)
        results.append((agent_name, ddl))
    
    return results
$$;

-- Call the batch procedure
CALL generate_all_agent_ddl('SALES_INTELLIGENCE', 'DATA');
```

### Output

The procedure returns a single STRING value containing the complete SQL `CREATE OR REPLACE AGENT` statement.

**Example output:**
```
CREATE OR REPLACE AGENT SALES_INTELLIGENCE.DATA.SALES_INTELLIGENCE_AGENT
COMMENT = 'Sales Intelligence Agent with multiple tools'
FROM SPECIFICATION
$$
models:
  orchestration: "claude-4-sonnet"
...
$$;
```

## Troubleshooting

### Common Errors

#### Error: `Object does not exist or not authorized`
**Possible causes:**
- Stored procedure not created
- Wrong database/schema context
- Insufficient permissions

**Solution:**
- Verify procedure exists: `SHOW PROCEDURES LIKE 'GENERATE_AGENT_SQL';`
- Check current context: `SELECT CURRENT_DATABASE(), CURRENT_SCHEMA();`
- Ensure you have EXECUTE permissions on the procedure

#### Error: `Agent not found or DESCRIBE failed`
**Possible causes:**
- Agent name is misspelled
- Agent doesn't exist in the specified database/schema
- Insufficient permissions to DESCRIBE the agent

**Solution:**
- Verify agent exists: `SHOW AGENTS IN SCHEMA <database>.<schema>;`
- Check spelling of database, schema, and agent name
- Verify DESCRIBE permissions: `DESCRIBE AGENT <database>.<schema>.<agent_name>;`

#### Error: `Invalid JSON specification`
**Possible causes:**
- Agent specification is corrupted
- Agent has invalid configuration

**Solution:**
- Check agent directly: `DESCRIBE AGENT <database>.<schema>.<agent_name>;`
- Review the agent_spec column for valid JSON
- Contact Snowflake support if specification appears corrupted

#### Error: `Syntax error: unexpected 'GENERATE_AGENT_SQL'`
**Possible causes:**
- Procedure not found in current context
- Wrong database/schema context

**Solution:**
- Use fully qualified name: `CALL <database>.<schema>.GENERATE_AGENT_SQL(...);`
- Or set context: `USE DATABASE <database>; USE SCHEMA <schema>;`

### Debugging Tips

1. **Verify procedure exists and is accessible:**
   ```sql
   SHOW PROCEDURES LIKE 'GENERATE_AGENT_SQL';
   DESCRIBE PROCEDURE GENERATE_AGENT_SQL(STRING, STRING, STRING);
   ```

2. **Test with a simple query first:**
   ```sql
   -- Verify agent exists
   SHOW AGENTS IN SCHEMA SALES_INTELLIGENCE.DATA;
   
   -- Test DESCRIBE directly
   DESCRIBE AGENT SALES_INTELLIGENCE.DATA.SALES_INTELLIGENCE_AGENT;
   ```

3. **Check permissions:**
   ```sql
   -- List your roles
   SHOW ROLES;
   
   -- Check grants
   SHOW GRANTS TO ROLE <your_role>;
   ```

## Advanced Usage

### Creating a Wrapper Procedure for Common Workflows

```sql
CREATE OR REPLACE PROCEDURE export_agent_ddl(
    source_db STRING,
    source_sch STRING,
    agent_name STRING,
    output_table STRING
)
RETURNS STRING
LANGUAGE SQL
AS
$$
DECLARE
    ddl_string STRING;
    insert_sql STRING;
BEGIN
    -- Generate DDL by calling the stored procedure
    CALL GENERATE_AGENT_SQL(source_db, source_sch, agent_name);
    
    -- Get the result from the last query
    SELECT $1 INTO ddl_string
    FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
    
    -- Insert into output table
    insert_sql := 'INSERT INTO ' || output_table || ' VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP())';
    EXECUTE IMMEDIATE :insert_sql USING (source_db, source_sch, agent_name, ddl_string);
    
    RETURN 'DDL generated and saved successfully';
END;
$$;
```

### Integration with Snowflake Tasks

```sql
-- Note: Tasks cannot directly use stored procedures in SELECT statements
-- You need to create a wrapper stored procedure that the task calls

-- Step 1: Create a procedure that handles the DDL generation for a single agent
CREATE OR REPLACE PROCEDURE generate_and_save_agent_ddl(
    target_database STRING,
    target_schema STRING,
    agent_name STRING
)
RETURNS STRING
LANGUAGE SQL
AS
$$
DECLARE
    ddl_string STRING;
BEGIN
    -- Call the GENERATE_AGENT_SQL procedure
    CALL GENERATE_AGENT_SQL(target_database, target_schema, agent_name);
    
    -- Get the result
    SELECT $1 INTO ddl_string
    FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
    
    -- Insert into archive table
    INSERT INTO agent_ddl_archive (
        snapshot_date, database_name, schema_name, agent_name, ddl_statement
    ) VALUES (
        CURRENT_DATE(), target_database, target_schema, agent_name, ddl_string
    );
    
    RETURN 'DDL saved for ' || agent_name;
END;
$$;

-- Step 2: Create a Python stored procedure to handle multiple agents
CREATE OR REPLACE PROCEDURE generate_all_agents_ddl_for_schema(
    target_database STRING,
    target_schema STRING
)
RETURNS STRING
LANGUAGE PYTHON
RUNTIME_VERSION = '3.10'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'generate_all'
AS
$$
def generate_all(session, target_database, target_schema):
    # Get list of agents
    agents = session.sql(f"SHOW AGENTS IN SCHEMA {target_database}.{target_schema}").collect()
    
    for agent in agents:
        agent_name = agent['name']
        # Call the wrapper procedure for each agent
        session.call('generate_and_save_agent_ddl', target_database, target_schema, agent_name)
    
    return f'Processed {len(agents)} agents'
$$;

-- Step 3: Create a task that calls the Python procedure
CREATE OR REPLACE TASK generate_agent_ddl_task
    WAREHOUSE = 'COMPUTE_WH'
    SCHEDULE = 'USING CRON 0 2 * * * UTC'  -- Daily at 2 AM UTC
AS
    CALL generate_all_agents_ddl_for_schema('SALES_INTELLIGENCE', 'DATA');

-- Resume the task
ALTER TASK generate_agent_ddl_task RESUME;
```

### Using in Streamlit Apps (Streamlit-in-Snowflake)

```python
import streamlit as st
from snowflake.snowpark import Session

@st.cache_data
def get_agent_ddl(database: str, schema: str, agent_name: str):
    session = Session.builder.getOrCreate()
    result = session.call('GENERATE_AGENT_SQL', database, schema, agent_name)
    return result

# Use in Streamlit app
ddl = get_agent_ddl('SALES_INTELLIGENCE', 'DATA', 'SALES_INTELLIGENCE_AGENT')
st.code(ddl, language='sql')
```

## Best Practices

1. **Use Fully Qualified Names**
   - Prefer: `CALL UTILITY_DB.AGENT_TOOLS.GENERATE_AGENT_SQL(...)`
   - Avoid ambiguity and ensure correct procedure is called

2. **Store Results in Tables**
   - Create audit tables to track generated DDL
   - Include timestamps and metadata for versioning

3. **Error Handling**
   - Wrap calls in try-catch blocks when using in procedures
   - Validate agent exists before calling

4. **Performance**
   - For batch operations, use table-valued functions or loops
   - Consider materializing results for frequently accessed DDL

5. **Version Control**
   - Store generated DDL in version control
   - Tag outputs with dates or version numbers

## Comparison with Python Script Version

| Feature | Stored Procedure | Python Script |
|---------|------------------|---------------|
| **Execution Location** | Inside Snowflake | External machine |
| **Authentication** | Uses current session | Requires PAT/credentials |
| **Dependencies** | None (uses Snowflake runtime) | Requires Python, snowflake-snowpark-python |
| **Integration** | Native SQL integration | Command-line tool |
| **CI/CD** | Can be called from SQL scripts | Requires Python environment |
| **Best For** | Snowflake-native workflows | External automation, local development |

## Related Tools

- `cortex_agents_ddl.py` - Python command-line version
- `SiS_Version.py` - Streamlit-in-Snowflake web interface version

## Support

For issues or questions:
1. Check the troubleshooting section
2. Verify permissions on agents and procedures
3. Test with a simple agent first
4. Review Snowflake documentation for stored procedures and agent permissions

## License

This stored procedure is part of the Snowflake Cortex Agent Migration toolkit.

