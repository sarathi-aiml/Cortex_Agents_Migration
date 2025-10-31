-- Replace <DATABASE>.<SCHEMA> before running, or run after using USE commands
-- Example:
--   USE DATABASE <DATABASE>;
--   USE SCHEMA <SCHEMA>;

CREATE OR REPLACE PROCEDURE GENERATE_AGENT_SQL(
    DB STRING,
    SCH STRING,
    AGENT_NAME STRING
)
RETURNS STRING
LANGUAGE PYTHON
RUNTIME_VERSION = '3.10'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'generate_agent_sql_proc'
AS
$$
import json
from typing import Dict, List, Optional


def truncate_description(description: str, max_length: int = 200) -> str:
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
        # Change this line to match SiS_Version.py
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


def _get_agent_details(session, database: str, schema: str, agent_name: str) -> Optional[Dict]:
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


def generate_agent_sql_proc(session, db: str, sch: str, agent_name: str) -> str:
    details = _get_agent_details(session, db, sch, agent_name)
    if not details:
        raise Exception(f"Agent not found or DESCRIBE failed: {db}.{sch}.{agent_name}")
    return generate_agent_sql(
        agent_name=agent_name,
        database=db,
        schema=sch,
        agent_spec_str=details.get("specification", "{}"),
        comment=details.get("comment", ""),
    )
$$;


