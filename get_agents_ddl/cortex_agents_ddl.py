#!/usr/bin/env python3
"""
Generate SQL CREATE AGENT statement from an existing Snowflake Cortex Agent.
Reads credentials from env.dev and takes DB, schema, and agent name as command line arguments.
"""

import argparse
import json
import os
import re
from typing import Dict, List, Optional
from snowflake.snowpark import Session
from dotenv import load_dotenv


def create_session_from_env(env_file: str = "env.dev") -> Session:
    """Create Snowflake session using credentials from env.dev file."""
    # Load environment variables from file
    load_dotenv(env_file)
    
    account_url = os.getenv("SOURCE_ACCOUNT_URL")
    pat_token = os.getenv("SOURCE_PAT")
    user = os.getenv("SOURCE_USER")
    warehouse = os.getenv("SOURCE_WAREHOUSE")
    database = os.getenv("SOURCE_DATABASE")
    schema = os.getenv("SOURCE_SCHEMA")
    
    if not account_url:
        raise ValueError("SOURCE_ACCOUNT_URL not found in env.dev")
    if not pat_token:
        raise ValueError("SOURCE_PAT not found in env.dev")
    if not user:
        raise ValueError("SOURCE_USER not found in env.dev")
    
    # Extract account identifier from URL
    # Format: https://<ACCOUNT_IDENTIFIER>.snowflakecomputing.com
    match = re.search(r'https://([^.]+)', account_url)
    if not match:
        raise ValueError(f"Invalid account URL format: {account_url}")
    
    account_identifier = match.group(1)
    
    # Create session with PAT authentication
    # PAT token goes in password field, not as oauth token
    connection_parameters = {
        "account": account_identifier,
        "user": user,
        "password": pat_token,  # PAT goes in password field
        "warehouse": warehouse,
        "database": database,
        "schema": schema
    }
    
    session = Session.builder.configs(connection_parameters).create()
    
    return session


def truncate_description(description: str, max_length: int = 200) -> str:
    """Truncate overly long descriptions to make them concise."""
    if not description:
        return ""
    if len(description) <= max_length:
        return description
    truncated = description[:max_length]
    last_period = truncated.rfind('.')
    last_newline = truncated.rfind('\n')
    if last_period > max_length * 0.7:
        return description[: last_period + 1]
    elif last_newline > max_length * 0.7:
        return description[:last_newline]
    else:
        return description[: max_length - 3] + "..."


def generate_agent_sql(
    agent_name: str,
    database: str,
    schema: str,
    agent_spec_str: str,
    comment: str = "",
) -> str:
    """Convert agent JSON specification to SQL CREATE AGENT statement.
    
    This function matches the exact logic from generate_agent_sql_procedure.sql
    """
    try:
        agent_spec = json.loads(agent_spec_str)
    except json.JSONDecodeError as e:
        return f"-- Error: Invalid JSON specification - {str(e)}"

    sql_parts: List[str] = [f"CREATE OR REPLACE AGENT {database}.{schema}.{agent_name}"]
    if comment:
        escaped_comment = comment.replace("'", "''")
        sql_parts.append(f"COMMENT = '{escaped_comment}'")
    sql_parts.append("FROM SPECIFICATION")
    sql_parts.append("$" + "$")

    yaml_content: List[str] = []

    if "models" in agent_spec and agent_spec["models"]:
        yaml_content.append("models:")
        for key, value in agent_spec["models"].items():
            if value is not None:
                yaml_content.append(f'  {key}: "{value}"')
        yaml_content.append("")

    if "instructions" in agent_spec and agent_spec["instructions"]:
        yaml_content.append("instructions:")
        instructions = agent_spec["instructions"]
        if instructions.get("response"):
            yaml_content.append(f'  response: "{instructions["response"]}"')
        if instructions.get("orchestration"):
            yaml_content.append(f'  orchestration: "{instructions["orchestration"]}"')
        if instructions.get("system"):
            yaml_content.append(f'  system: "{instructions["system"]}"')
        if instructions.get("sample_questions"):
            yaml_content.append("  sample_questions:")
            for question in instructions["sample_questions"]:
                if isinstance(question, dict) and "question" in question:
                    yaml_content.append(f'    - question: "{question["question"]}"')
                elif isinstance(question, str):
                    yaml_content.append(f'    - question: "{question}"')
        yaml_content.append("")

    if "tools" in agent_spec and agent_spec["tools"]:
        yaml_content.append("tools:")
        for tool in agent_spec["tools"]:
            if "tool_spec" in tool:
                tool_spec = tool["tool_spec"]
                yaml_content.append("  - tool_spec:")
                yaml_content.append(f'      type: "{tool_spec.get("type", "")}"')
                yaml_content.append(f'      name: "{tool_spec.get("name", "")}"')
                desc = tool_spec.get("description", "")
                if desc:
                    desc = truncate_description(desc, 300)
                    if len(desc) > 200 or "\n" in desc:
                        yaml_content.append("      description: |")
                        for line in desc.split("\n"):
                            yaml_content.append(f"        {line}")
                    else:
                        yaml_content.append(f'      description: "{desc}"')
                if "input_schema" in tool_spec:
                    yaml_content.append("      input_schema:")
                    schema_obj = tool_spec["input_schema"]
                    yaml_content.append("        type: object")
                    if "properties" in schema_obj:
                        yaml_content.append("        properties:")
                        for prop_name, prop_def in schema_obj["properties"].items():
                            yaml_content.append(f"          {prop_name}:")
                            if "description" in prop_def:
                                pdesc = truncate_description(prop_def["description"], 150)
                                if "\n" in pdesc or len(pdesc) > 80:
                                    yaml_content.append("            description: |")
                                    for line in pdesc.split("\n"):
                                        yaml_content.append(f"              {line}")
                                else:
                                    yaml_content.append(f'            description: "{pdesc}"')
                            yaml_content.append(f"            type: {prop_def.get('type', 'string')}")
                    if "required" in schema_obj and schema_obj["required"]:
                        yaml_content.append("        required:")
                        for req_field in schema_obj["required"]:
                            yaml_content.append(f"          - {req_field}")
                yaml_content.append("")

    if "tool_resources" in agent_spec and agent_spec["tool_resources"]:
        yaml_content.append("tool_resources:")
        for tool_name, resources in agent_spec["tool_resources"].items():
            yaml_content.append(f"  {tool_name}:")
            if "execution_environment" in resources:
                yaml_content.append("    execution_environment:")
                exec_env = resources["execution_environment"]
                if "query_timeout" in exec_env:
                    yaml_content.append(f"      query_timeout: {exec_env['query_timeout']}")
                if "type" in exec_env:
                    yaml_content.append(f'      type: "{exec_env["type"]}"')
                if "warehouse" in exec_env:
                    yaml_content.append(f'      warehouse: "{exec_env["warehouse"]}"')
            tool_type = resources.get("type", "")
            if tool_type == "function":
                field_order = ["identifier", "name", "type"]
            elif tool_type == "procedure":
                field_order = ["identifier", "name", "type"]
            elif "semantic_model_file" in resources:
                field_order = ["semantic_model_file"]
            elif "id_column" in resources:
                field_order = ["id_column", "max_results", "name", "title_column"]
            else:
                field_order = [
                    "identifier",
                    "name",
                    "type",
                    "semantic_model_file",
                    "id_column",
                    "max_results",
                    "title_column",
                    "search_service",
                    "filter",
                ]
            for field in field_order:
                if field in resources and field != "execution_environment":
                    resource_value = resources[field]
                    if isinstance(resource_value, str):
                        yaml_content.append(f'    {field}: "{resource_value}"')
                    elif isinstance(resource_value, int):
                        yaml_content.append(f"    {field}: {resource_value}")
                    elif isinstance(resource_value, dict):
                        yaml_content.append(f"    {field}:")
                        for k, v in resource_value.items():
                            if isinstance(v, dict):
                                yaml_content.append(f"      {k}:")
                                for sub_k, sub_v in v.items():
                                    yaml_content.append(f'        {sub_k}: "{sub_v}"')
                            else:
                                yaml_content.append(f'      {k}: "{v}"')
            yaml_content.append("")

    if "orchestration" in agent_spec and agent_spec["orchestration"]:
        orch = agent_spec["orchestration"]
        if isinstance(orch, dict) and "budget" in orch and orch["budget"]:
            budget = orch["budget"]
            yaml_content.append("orchestration:")
            yaml_content.append("  budget:")
            if "seconds" in budget:
                yaml_content.append(f"    seconds: {budget['seconds']}")
            if "tokens" in budget:
                yaml_content.append(f"    tokens: {budget['tokens']}")

    if "profile" in agent_spec and agent_spec["profile"]:
        yaml_content.append("profile:")
        for profile_key, profile_value in agent_spec["profile"].items():
            if profile_value:
                yaml_content.append(f'  {profile_key}: "{profile_value}"')

    sql_parts.append("\n".join(yaml_content))
    sql_parts.append("$" + "$;")
    return "\n".join(sql_parts)


def _get_agent_details(session: Session, database: str, schema: str, agent_name: str) -> Optional[Dict]:
    """Get agent details using DESCRIBE AGENT command."""
    result = session.sql(
        f"DESCRIBE AGENT {database}.{schema}.{agent_name}"
    ).collect()
    if not result:
        return None
    row = result[0]
    row_dict = row.asDict() if hasattr(row, "asDict") else dict(row)
    agent_spec = None
    for spec_key in [
        "agent_spec",
        "AGENT_SPEC",
        "specification",
        "SPECIFICATION",
        "spec",
        "SPEC",
        "definition",
        "DEFINITION",
    ]:
        if spec_key in row_dict and row_dict[spec_key]:
            agent_spec = row_dict[spec_key]
            break
    return {
        "name": agent_name,
        "specification": agent_spec or "{}",
        "comment": row_dict.get("comment") or "",
    }


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate SQL CREATE AGENT statement from an existing Snowflake Cortex Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cortex_agents_ddl.py --database SALES_INTELLIGENCE --schema DATA --agent SALES_INTELLIGENCE_AGENT
  python cortex_agents_ddl.py -d SALES_INTELLIGENCE -s DATA -a SALES_INTELLIGENCE_AGENT
        """.strip()
    )
    parser.add_argument(
        "--database", "-d",
        required=True,
        help="Database name"
    )
    parser.add_argument(
        "--schema", "-s",
        required=True,
        help="Schema name"
    )
    parser.add_argument(
        "--agent", "-a",
        required=True,
        help="Agent name"
    )
    parser.add_argument(
        "--env-file",
        default="env.dev",
        help="Path to environment file (default: env.dev)"
    )
    return parser.parse_args()


def main() -> None:
    """Main function."""
    args = parse_args()
    
    try:
        # Create Snowflake session from env.dev
        session = create_session_from_env(args.env_file)
        
        # Get agent details
        details = _get_agent_details(session, args.database, args.schema, args.agent)
        if not details:
            raise SystemExit(
                f"Error: Agent not found or DESCRIBE failed: {args.database}.{args.schema}.{args.agent}"
            )
        
        # Generate SQL
        sql_statement = generate_agent_sql(
            agent_name=args.agent,
            database=args.database,
            schema=args.schema,
            agent_spec_str=details.get("specification", "{}"),
            comment=details.get("comment", ""),
        )
        
        # Output SQL to stdout
        print(sql_statement)
        
    except FileNotFoundError as e:
        raise SystemExit(f"Error: {str(e)}")
    except ValueError as e:
        raise SystemExit(f"Error: {str(e)}")
    except Exception as e:
        raise SystemExit(f"Error: {str(e)}")


if __name__ == "__main__":
    main()
