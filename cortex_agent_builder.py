import streamlit as st
import requests
import json
import os
import re
from typing import Dict, List, Optional, Tuple
import pandas as pd
from datetime import datetime
from snowflake.snowpark import Session

# Load environment variables
def load_env():
    """Load environment variables from env.dev file"""
    env_vars = {}
    # Try multiple paths
    env_paths = ['env.dev', 'backup/env.dev', os.path.join(os.path.dirname(__file__), 'env.dev')]
    
    for env_path in env_paths:
        try:
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key] = value
                return env_vars
        except FileNotFoundError:
            continue
    
    st.error("env.dev file not found. Please ensure it exists in the current directory or backup folder.")
    return None

class SnowflakeCortexAgentAPI:
    """Client for Snowflake Cortex Agents REST API"""
    
    def __init__(self, account_url: str, pat_token: str, account_name: str = "Unknown"):
        self.account_url = account_url.rstrip('/')
        self.pat_token = pat_token
        self.account_name = account_name
        self.base_url = f"{self.account_url}/api/v2"
        self.headers = {
            'Authorization': f'Bearer {pat_token}',
            'Content-Type': 'application/json'
        }
    
    def test_connection(self) -> Tuple[bool, str]:
        """Test the connection to the Snowflake account"""
        try:
            # Try to list databases as a connection test
            url = f"{self.base_url}/databases"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return True, "Connection successful"
        except requests.exceptions.RequestException as e:
            return False, f"Connection failed: {str(e)}"
    
    def create_agent(self, database: str, schema: str, agent_config: Dict) -> bool:
        """Create a new agent"""
        url = f"{self.base_url}/databases/{database}/schemas/{schema}/agents"
        
        try:
            response = requests.post(url, headers=self.headers, json=agent_config)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            st.error(f"Error creating agent in {self.account_name}: {str(e)}")
            return False

@st.cache_resource
def create_snowflake_session(_env_vars: Dict) -> Optional[Session]:
    """Create Snowflake session using credentials from env.dev file"""
    try:
        account_url = _env_vars.get('TARGET_ACCOUNT_URL', '')
        pat_token = _env_vars.get('TARGET_PAT', '')
        user = _env_vars.get('TARGET_USER', '')
        warehouse = _env_vars.get('TARGET_WAREHOUSE', '')
        database = _env_vars.get('TARGET_DATABASE', '')
        schema = _env_vars.get('TARGET_SCHEMA', '')
        
        if not account_url:
            st.error("TARGET_ACCOUNT_URL not found in env.dev")
            return None
        if not pat_token:
            st.error("TARGET_PAT not found in env.dev")
            return None
        if not user:
            st.warning("TARGET_USER not found in env.dev. Using TARGET_DATABASE as fallback.")
            # Try to use SOURCE_USER as fallback if available
            user = _env_vars.get('SOURCE_USER', '')
            if not user:
                st.error("TARGET_USER or SOURCE_USER not found in env.dev")
                return None
        
        # Extract account identifier from URL
        match = re.search(r'https://([^.]+)', account_url)
        if not match:
            st.error(f"Invalid account URL format: {account_url}")
            return None
        
        account_identifier = match.group(1)
        
        # Create session with PAT authentication
        connection_parameters = {
            "account": account_identifier,
            "user": user,
            "password": pat_token,
            "warehouse": warehouse if warehouse else None,
            "database": database if database else None,
            "schema": schema if schema else None
        }
        
        # Remove None values
        connection_parameters = {k: v for k, v in connection_parameters.items() if v is not None}
        
        session = Session.builder.configs(connection_parameters).create()
        return session
    except Exception as e:
        st.error(f"Error creating Snowflake session: {str(e)}")
        return None

def get_databases(session: Session) -> List[str]:
    """Get list of databases accessible to the current session"""
    try:
        result = session.sql("SHOW DATABASES").collect()
        databases = [row['name'] for row in result if row['name'] not in ['INFORMATION_SCHEMA']]
        return databases
    except Exception as e:
        st.error(f"Error fetching databases: {str(e)}")
        return []

def get_schemas(session: Session, database: str) -> List[str]:
    """Get list of schemas in the specified database"""
    try:
        result = session.sql(f"SHOW SCHEMAS IN DATABASE {database}").collect()
        schemas = [row['name'] for row in result if row['name'] not in ['INFORMATION_SCHEMA']]
        return schemas
    except Exception as e:
        st.error(f"Error fetching schemas: {str(e)}")
        return []

def get_cortex_search_services(session: Session, database: str, schema: str) -> List[str]:
    """Get list of Cortex Search services in the specified schema"""
    try:
        result = session.sql(f"SHOW CORTEX SEARCH SERVICES IN SCHEMA {database}.{schema}").collect()
        services = [row['name'] for row in result]
        return services
    except Exception as e:
        st.error(f"Error fetching Cortex Search services: {str(e)}")
        return []

def get_semantic_views(session: Session, database: str, schema: str) -> List[str]:
    """Get list of semantic views in the specified schema"""
    try:
        result = session.sql(f"SHOW SEMANTIC VIEWS IN SCHEMA {database}.{schema}").collect()
        views = [row['name'] for row in result]
        return views
    except Exception as e:
        st.error(f"Error fetching semantic views: {str(e)}")
        return []

def get_stages(session: Session, database: str, schema: str) -> List[str]:
    """Get list of stages in the specified schema"""
    try:
        result = session.sql(f"SHOW STAGES IN SCHEMA {database}.{schema}").collect()
        stages = [row['name'] for row in result]
        return stages
    except Exception as e:
        st.error(f"Error fetching stages: {str(e)}")
        return []

def get_stage_files(session: Session, stage_path: str) -> List[str]:
    """Get list of files in the specified stage"""
    try:
        result = session.sql(f"LIST @{stage_path}").collect()
        files = []
        for row in result:
            # Extract file name from the path
            # Try lowercase 'name' first, then uppercase 'NAME'
            try:
                file_path = row['name']
            except (KeyError, TypeError):
                try:
                    file_path = row['NAME']
                except (KeyError, TypeError):
                    file_path = ''
            
            if file_path:
                # Get just the filename
                file_name = file_path.split('/')[-1]
                if file_name and file_name.endswith(('.yaml', '.yml')):
                    files.append(file_name)
        return files
    except Exception as e:
        st.error(f"Error fetching stage files: {str(e)}")
        return []

def get_views(session: Session, database: str, schema: str) -> List[str]:
    """Get list of views in the specified schema"""
    try:
        result = session.sql(f"SHOW VIEWS IN SCHEMA {database}.{schema}").collect()
        views = [row['name'] for row in result]
        return views
    except Exception as e:
        st.error(f"Error fetching views: {str(e)}")
        return []

def get_procedures(session: Session, database: str, schema: str) -> List[str]:
    """Get list of procedures in the specified schema"""
    try:
        result = session.sql(f"SHOW PROCEDURES IN SCHEMA {database}.{schema}").collect()
        procedures = []
        for row in result:
            try:
                proc_name = row['name']
                # Try to get arguments, handle if not present
                try:
                    arguments = row['arguments']
                except (KeyError, TypeError):
                    try:
                        arguments = row['ARGUMENTS']
                    except (KeyError, TypeError):
                        arguments = ''
                procedures.append(f"{proc_name}({arguments})" if arguments else proc_name)
            except (KeyError, TypeError):
                continue
        return procedures
    except Exception as e:
        st.error(f"Error fetching procedures: {str(e)}")
        return []

def get_udfs(session: Session, database: str, schema: str) -> List[str]:
    """Get list of user-defined functions in the specified schema"""
    try:
        result = session.sql(f"SHOW USER FUNCTIONS IN SCHEMA {database}.{schema}").collect()
        udfs = []
        for row in result:
            try:
                udf_name = row['name']
                # Try to get arguments, handle if not present
                try:
                    arguments = row['arguments']
                except (KeyError, TypeError):
                    try:
                        arguments = row['ARGUMENTS']
                    except (KeyError, TypeError):
                        arguments = ''
                udfs.append(f"{udf_name}({arguments})" if arguments else udf_name)
            except (KeyError, TypeError):
                continue
        return udfs
    except Exception as e:
        st.error(f"Error fetching UDFs: {str(e)}")
        return []

def get_warehouses(session: Session) -> List[str]:
    """Get list of warehouses accessible to the current session"""
    try:
        result = session.sql("SHOW WAREHOUSES").collect()
        warehouses = [row['name'] for row in result]
        return warehouses
    except Exception as e:
        st.error(f"Error fetching warehouses: {str(e)}")
        return []

def generate_agent_sql(agent_name: str, database: str, schema: str, agent_spec_str: str, comment: str = '') -> str:
    """Convert agent JSON specification to SQL CREATE AGENT statement"""
    try:
        agent_spec = json.loads(agent_spec_str)
    except json.JSONDecodeError:
        return "-- Error: Invalid JSON specification"
    
    # Start building the SQL statement
    sql_parts = [f"CREATE OR REPLACE AGENT {database}.{schema}.{agent_name}"]
    
    # Add comment if provided
    if comment:
        escaped_comment = comment.replace("'", "''")
        sql_parts.append(f"COMMENT = '{escaped_comment}'")
    
    sql_parts.append("FROM SPECIFICATION")
    sql_parts.append("$$")
    
    # Convert JSON to YAML-like format
    yaml_content = []
    
    # Note: profile is not supported in agent specification, so we skip it
    
    # Handle models
    if 'models' in agent_spec and agent_spec['models']:
        yaml_content.append("models:")
        for key, value in agent_spec['models'].items():
            if value is not None:
                yaml_content.append(f'  {key}: "{value}"')
        yaml_content.append("")  # Add blank line after models
    
    # Handle instructions FIRST (before tools)
    if 'instructions' in agent_spec and agent_spec['instructions']:
        yaml_content.append("instructions:")
        instructions = agent_spec['instructions']
        
        # Handle response
        if 'response' in instructions and instructions['response']:
            yaml_content.append(f'  response: "{instructions["response"]}"')
        
        # Handle orchestration
        if 'orchestration' in instructions and instructions['orchestration']:
            yaml_content.append(f'  orchestration: "{instructions["orchestration"]}"')
        
        # Handle sample_questions (inside instructions)
        if 'sample_questions' in instructions and instructions['sample_questions']:
            yaml_content.append("  sample_questions:")
            for question in instructions['sample_questions']:
                if isinstance(question, dict) and 'question' in question:
                    yaml_content.append(f'    - question: "{question["question"]}"')
                elif isinstance(question, str):
                    yaml_content.append(f'    - question: "{question}"')
        yaml_content.append("")  # Add blank line after instructions
    
    # Handle tools
    if 'tools' in agent_spec and agent_spec['tools']:
        yaml_content.append("tools:")
        for tool in agent_spec['tools']:
            if 'tool_spec' in tool:
                tool_spec = tool['tool_spec']
                yaml_content.append("  - tool_spec:")
                yaml_content.append(f'      type: "{tool_spec.get("type", "")}"')
                yaml_content.append(f'      name: "{tool_spec.get("name", "")}"')
                
                # Handle description with pipe (|) for multiline - NO quotes needed
                desc = tool_spec.get('description', '')
                if desc:
                    yaml_content.append("      description: |")
                    # Split by newlines if they exist
                    for line in desc.split('\n'):
                        yaml_content.append(f"        {line}")
                
                # Add input_schema if present
                if 'input_schema' in tool_spec:
                    yaml_content.append("      input_schema:")
                    schema_obj = tool_spec['input_schema']
                    yaml_content.append("        type: object")  # No quotes on object
                    
                    if 'properties' in schema_obj:
                        yaml_content.append("        properties:")
                        for prop_name, prop_def in schema_obj['properties'].items():
                            yaml_content.append(f"          {prop_name}:")
                            
                            # Handle description first (CRITICAL: no quotes when using pipe)
                            if 'description' in prop_def:
                                desc = prop_def['description']
                                if '\n' in desc or len(desc) > 80:
                                    # Multiline - use pipe, NO quotes
                                    yaml_content.append("            description: |")
                                    for line in desc.split('\n'):
                                        yaml_content.append(f"              {line}")
                                else:
                                    # Single line - use quotes
                                    yaml_content.append(f'            description: "{desc}"')
                            
                            # Then type - NO quotes
                            yaml_content.append(f"            type: {prop_def.get('type', 'string')}")
                    
                    if 'required' in schema_obj and schema_obj['required']:
                        yaml_content.append("        required:")
                        for req_field in schema_obj['required']:
                            yaml_content.append(f"          - {req_field}")
                
                yaml_content.append("")  # Add blank line between tools
    
    # Handle tool_resources - KEEP ALL FIELDS from API response
    if 'tool_resources' in agent_spec and agent_spec['tool_resources']:
        yaml_content.append("tool_resources:")
        for tool_name, resources in agent_spec['tool_resources'].items():
            yaml_content.append(f"  {tool_name}:")
            
            # Handle execution_environment first if present
            if 'execution_environment' in resources:
                yaml_content.append("    execution_environment:")
                exec_env = resources['execution_environment']
                if 'query_timeout' in exec_env:
                    yaml_content.append(f"      query_timeout: {exec_env['query_timeout']}")
                if 'type' in exec_env:
                    yaml_content.append(f'      type: "{exec_env["type"]}"')
                if 'warehouse' in exec_env:
                    yaml_content.append(f'      warehouse: "{exec_env["warehouse"]}"')
            
            # Handle other resource fields in specific order
            # Note: For Cortex Search: id_column, max_results, name, title_column
            # For Cortex Analyst: semantic_model_file (for YAML) or semantic_view (for View)
            # For Generic: identifier, name, type
            field_order = ['identifier', 'name', 'type', 'semantic_model_file', 'semantic_view', 'id_column', 'max_results', 'title_column']
            
            for field in field_order:
                if field in resources and field != 'execution_environment':
                    resource_value = resources[field]
                    if isinstance(resource_value, str):
                        # Escape quotes in string values
                        escaped_value = resource_value.replace('"', '\\"')
                        yaml_content.append(f'    {field}: "{escaped_value}"')
                    elif isinstance(resource_value, int):
                        yaml_content.append(f"    {field}: {resource_value}")
            
            yaml_content.append("")  # Add blank line between tool resources
    
    # Handle orchestration budget (at root level, separate from instructions)
    if 'orchestration' in agent_spec and agent_spec['orchestration']:
        orch = agent_spec['orchestration']
        if 'budget' in orch and orch['budget']:  # Only if budget exists and not empty
            yaml_content.append("orchestration:")
            yaml_content.append("  budget:")
            budget = orch['budget']
            if 'seconds' in budget:
                yaml_content.append(f"    seconds: {budget['seconds']}")
            if 'tokens' in budget:
                yaml_content.append(f"    tokens: {budget['tokens']}")
    
    # Combine all parts
    sql_parts.append('\n'.join(yaml_content))
    sql_parts.append("$$;")
    
    return '\n'.join(sql_parts)

def build_agent_config(
    agent_name: str,
    comment: str,
    display_name: str,
    orchestration_instructions: str,
    response_instructions: str,
    orchestration_model: str,
    time_budget: int,
    token_budget: int,
    tools: List[Dict],
    target_database: str,
    target_schema: str
) -> Dict:
    """Build agent configuration dictionary from form inputs"""
    agent_config = {
        "name": agent_name,
        "comment": comment,
        "instructions": {
            "orchestration": orchestration_instructions,
            "response": response_instructions
        },
        "models": {
            "orchestration": orchestration_model if orchestration_model != "auto" else None
        },
        "orchestration": {
            "budget": {
                "seconds": time_budget,
                "tokens": token_budget
            }
        },
        "tools": [],
        "tool_resources": {}
    }
    
    # Build tools and tool_resources
    for tool in tools:
        tool_spec = {
            "type": tool['tool_type'],
            "name": tool['tool_name'],
            "description": tool['tool_description']
        }
        
        # Add input_schema based on tool type
        if tool['tool_type'] == 'cortex_search':
            tool_spec['input_schema'] = {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string"
                    }
                },
                "required": ["query"]
            }
        elif tool['tool_type'] == 'cortex_analyst_text_to_sql':
            tool_spec['input_schema'] = {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Natural language question to convert to SQL"
                    }
                },
                "required": ["question"]
            }
        elif tool['tool_type'] == 'generic':
            # Generic tools don't require input_schema in the UI
            # If needed, it can be added manually to the generated SQL
            pass
        
        agent_config['tools'].append({"tool_spec": tool_spec})
        
        # Build tool_resources
        tool_resource = {}
        
        if tool['tool_type'] == 'cortex_search':
            # For Cortex Search, use name (full qualified name)
            tool_resource['name'] = f"{tool['database']}.{tool['schema']}.{tool['cortex_search_service']}"
            # Optional fields for Cortex Search
            if tool.get('search_id_column'):
                tool_resource['id_column'] = tool['search_id_column']
            if tool.get('search_max_results'):
                tool_resource['max_results'] = tool['search_max_results']
            if tool.get('search_title_column'):
                tool_resource['title_column'] = tool['search_title_column']
        
        elif tool['tool_type'] == 'cortex_analyst_text_to_sql':
            # Always add execution_environment for Cortex Analyst
            if tool.get('warehouse'):
                tool_resource['execution_environment'] = {
                    "type": "warehouse",
                    "warehouse": tool['warehouse']
                }
            
            if tool['analyst_type'] == 'yaml':
                # For YAML, use semantic_model_file pointing to stage path
                stage = tool.get('stage', '')
                yaml_file = tool.get('yaml_file', '')
                database = tool.get('database', '')
                schema = tool.get('schema', '')
                if stage and yaml_file and database and schema:
                    stage_path = f"{database}.{schema}.{stage}"
                    tool_resource['semantic_model_file'] = f"@{stage_path}/{yaml_file}"
                else:
                    missing = []
                    if not stage: missing.append('stage')
                    if not yaml_file: missing.append('yaml_file')
                    if not database: missing.append('database')
                    if not schema: missing.append('schema')
                    st.error(f"❌ Tool {tool.get('tool_name', 'unknown')}: Missing required fields: {', '.join(missing)}")
            elif tool['analyst_type'] == 'view':
                # For View, use semantic_view field (not identifier)
                semantic_view = tool.get('semantic_view', '')
                database = tool.get('database', '')
                schema = tool.get('schema', '')
                if semantic_view and database and schema:
                    tool_resource['semantic_view'] = f"{database}.{schema}.{semantic_view}"
                else:
                    missing = []
                    if not semantic_view: missing.append('semantic_view')
                    if not database: missing.append('database')
                    if not schema: missing.append('schema')
                    st.error(f"❌ Tool {tool.get('tool_name', 'unknown')}: Missing required fields: {', '.join(missing)}")
        
        elif tool['tool_type'] == 'generic':
            if tool['custom_type'] == 'procedure':
                # For custom procedure - need full signature for name, identifier is just the name
                proc_full = tool['procedure']  # This should be "PROC_NAME(ARG1 TYPE, ARG2 TYPE)"
                proc_name = proc_full.split('(')[0] if '(' in proc_full else proc_full
                tool_resource['identifier'] = f"{tool['database']}.{tool['schema']}.{proc_name}"
                tool_resource['name'] = proc_full  # Full signature with arguments
                tool_resource['type'] = "procedure"
            elif tool['custom_type'] == 'udf':
                # For custom UDF - need full signature for name, identifier is just the name
                udf_full = tool['udf']  # This should be "UDF_NAME(ARG1 TYPE, ARG2 TYPE)"
                udf_name = udf_full.split('(')[0] if '(' in udf_full else udf_full
                tool_resource['identifier'] = f"{tool['database']}.{tool['schema']}.{udf_name}"
                tool_resource['name'] = udf_full  # Full signature with arguments
                tool_resource['type'] = "function"
        
        # Add execution_environment for generic tools if warehouse is available
        # (Cortex Analyst already has it added above)
        if tool['tool_type'] == 'generic' and tool.get('warehouse'):
            if 'execution_environment' not in tool_resource:
                tool_resource['execution_environment'] = {}
            tool_resource['execution_environment']['type'] = "warehouse"
            tool_resource['execution_environment']['warehouse'] = tool['warehouse']
            if tool.get('query_timeout'):
                tool_resource['execution_environment']['query_timeout'] = tool['query_timeout']
        
        # Always add tool_resource (it should always have at least identifier/name/semantic_model_file)
        agent_config['tool_resources'][tool['tool_name']] = tool_resource
    
    # Remove None values and empty dicts
    agent_config = {k: v for k, v in agent_config.items() if v is not None and v != {}}
    if agent_config.get("models", {}).get("orchestration") is None:
        agent_config["models"] = {}
    
    # Remove profile field - it's not supported in agent specification
    if "profile" in agent_config:
        del agent_config["profile"]
    
    return agent_config

def generate_agent_sql_from_config(
    agent_name: str,
    database: str,
    schema: str,
    agent_config: Dict,
    comment: str = ''
) -> str:
    """Generate SQL CREATE AGENT statement from agent configuration"""
    agent_spec_str = json.dumps(agent_config, indent=2)
    return generate_agent_sql(agent_name, database, schema, agent_spec_str, comment)

def main():
    st.set_page_config(
        page_title="Snowflake Cortex Agent Builder",
        page_icon="➕",
        layout="wide"
    )
    
    st.title("➕ Snowflake Cortex Agent Builder")
    st.markdown("Create new Cortex Agents with comprehensive tool configuration")
    
    # Load environment variables
    env_vars = load_env()
    if not env_vars:
        st.stop()
    
    # Extract target configuration
    target_config = {
        'url': env_vars.get('TARGET_ACCOUNT_URL', ''),
        'pat': env_vars.get('TARGET_PAT', ''),
        'database': env_vars.get('TARGET_DATABASE', ''),
        'schema': env_vars.get('TARGET_SCHEMA', '')
    }
    
    # Initialize API client
    target_client = None
    if target_config['url'] and target_config['pat']:
        target_client = SnowflakeCortexAgentAPI(
            account_url=target_config['url'],
            pat_token=target_config['pat'],
            account_name="Target"
        )
    
    # Create Snowflake session for querying database objects
    session = create_snowflake_session(env_vars)
    
    # Initialize session state
    if 'selected_database' not in st.session_state:
        st.session_state.selected_database = target_config.get('database', '')
    if 'selected_schema' not in st.session_state:
        st.session_state.selected_schema = target_config.get('schema', '')
    if 'tools' not in st.session_state:
        st.session_state.tools = []
    if 'generated_sql' not in st.session_state:
        st.session_state.generated_sql = None
    if 'sql_agent_name' not in st.session_state:
        st.session_state.sql_agent_name = ''
    
    # Step 1: Database and Schema Selection (FIRST)
    st.subheader("Step 1: Select Database and Schema")
    if session:
        databases = get_databases(session)
        if databases:
            current_db = st.session_state.selected_database
            db_index = databases.index(current_db) if current_db in databases else 0
            selected_db = st.selectbox(
                "Database *",
                databases,
                index=db_index,
                key="main_database"
            )
            if selected_db != st.session_state.selected_database:
                st.session_state.selected_database = selected_db
                st.session_state.selected_schema = ''  # Reset schema when database changes
                st.rerun()
            
            schemas = get_schemas(session, selected_db)
            if schemas:
                current_schema = st.session_state.selected_schema
                schema_index = schemas.index(current_schema) if current_schema in schemas else 0
                selected_schema = st.selectbox(
                    "Schema *",
                    schemas,
                    index=schema_index,
                    key="main_schema"
                )
                st.session_state.selected_schema = selected_schema
    else:
        st.warning("⚠️ Snowflake session not available. Using default database and schema from env.dev")
        selected_db = target_config.get('database', '')
        selected_schema = target_config.get('schema', '')
        st.session_state.selected_database = selected_db
        st.session_state.selected_schema = selected_schema
    
    st.divider()
    
    # Step 3: Tools (THIRD)
    st.subheader("Step 3: Tools")
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write(f"**Number of tools:** {len(st.session_state.tools)}")
    with col2:
        if st.button("➕ Add Tool", type="secondary"):
            st.session_state.tools.append({
                'tool_name': '',
                'tool_comment': '',
                'tool_description': '',
                'database': st.session_state.selected_database,
                'schema': st.session_state.selected_schema,
                'tool_type': 'Cortex Analyst'
            })
            st.rerun()
    
    # Display and configure tools
    if st.session_state.tools:
        for idx, tool in enumerate(st.session_state.tools):
            with st.expander(f"Tool {idx + 1}: {tool.get('tool_name', 'Unnamed')}", expanded=True):
                col1, col2 = st.columns([4, 1])
                with col1:
                    tool_name = st.text_input(
                        "Tool Name *",
                        value=tool.get('tool_name', ''),
                        key=f"tool_name_{idx}",
                        help="Required: Unique name for this tool"
                    )
                    tool_comment = st.text_area(
                        "Tool Comment",
                        value=tool.get('tool_comment', ''),
                        key=f"tool_comment_{idx}",
                        help="Optional comment for this tool"
                    )
                    tool_description = st.text_area(
                        "Tool Description *",
                        value=tool.get('tool_description', ''),
                        key=f"tool_description_{idx}",
                        help="Required: Description of what this tool does"
                    )
                with col2:
                    if st.button("🗑️ Remove", key=f"remove_{idx}", type="secondary"):
                        st.session_state.tools.pop(idx)
                        st.rerun()
                
                # Database and Schema selection (use main selection as default)
                if session:
                    databases = get_databases(session)
                    if databases:
                        current_db = tool.get('database', st.session_state.selected_database)
                        db_index = databases.index(current_db) if current_db in databases else 0
                        selected_db = st.selectbox(
                            "Database *",
                            databases,
                            index=db_index,
                            key=f"tool_db_{idx}"
                        )
                        if selected_db != tool.get('database'):
                            tool['database'] = selected_db
                            tool['schema'] = ''  # Reset schema when database changes
                            st.rerun()
                        
                        schemas = get_schemas(session, selected_db)
                        if schemas:
                            current_schema = tool.get('schema', st.session_state.selected_schema)
                            schema_index = schemas.index(current_schema) if current_schema in schemas else 0
                            selected_schema = st.selectbox(
                                "Schema *",
                                schemas,
                                index=schema_index,
                                key=f"tool_schema_{idx}"
                            )
                            tool['schema'] = selected_schema
                else:
                    # Use main selection if session not available
                    tool['database'] = st.session_state.selected_database
                    tool['schema'] = st.session_state.selected_schema
                
                # Tool Type selection
                # Map display names to internal tool types
                tool_type_display = tool.get('tool_type', 'Cortex Analyst')
                if tool_type_display in ['cortex_analyst_text_to_sql', 'cortex_search', 'generic']:
                    # It's already an internal type, map to display
                    type_map = {
                        'cortex_analyst_text_to_sql': 'Cortex Analyst',
                        'cortex_search': 'Cortex Search',
                        'generic': 'Custom Tool'
                    }
                    tool_type_display = type_map.get(tool_type_display, 'Cortex Analyst')
                
                tool_type = st.selectbox(
                    "Tool Type *",
                    ["Cortex Analyst", "Cortex Search", "Custom Tool"],
                    index=["Cortex Analyst", "Cortex Search", "Custom Tool"].index(tool_type_display) if tool_type_display in ["Cortex Analyst", "Cortex Search", "Custom Tool"] else 0,
                    key=f"tool_type_{idx}"
                )
                # Don't set tool['tool_type'] here - it will be set in the conditional sections below
                
                # Conditional fields based on tool type
                if tool_type == "Cortex Search":
                    if session and tool.get('database') and tool.get('schema'):
                        search_services = get_cortex_search_services(session, tool['database'], tool['schema'])
                        if search_services:
                            selected_search = st.selectbox(
                                "Cortex Search Service *",
                                search_services,
                                index=search_services.index(tool['cortex_search_service']) if tool.get('cortex_search_service') in search_services else 0,
                                key=f"cortex_search_{idx}"
                            )
                            tool['cortex_search_service'] = selected_search
                            tool['tool_type'] = 'cortex_search'
                            
                            # Optional fields for Cortex Search
                            st.write("**Optional Cortex Search Fields:**")
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                tool['search_id_column'] = st.text_input(
                                    "ID Column",
                                    value=tool.get('search_id_column', ''),
                                    key=f"search_id_col_{idx}",
                                    help="Column name for search result IDs"
                                )
                            with col2:
                                tool['search_max_results'] = st.number_input(
                                    "Max Results",
                                    min_value=1,
                                    max_value=100,
                                    value=tool.get('search_max_results', 5),
                                    key=f"search_max_{idx}",
                                    help="Maximum number of search results"
                                )
                            with col3:
                                tool['search_title_column'] = st.text_input(
                                    "Title Column",
                                    value=tool.get('search_title_column', ''),
                                    key=f"search_title_col_{idx}",
                                    help="Column name for search result titles"
                                )
                        else:
                            st.warning("No Cortex Search services found in selected schema")
                
                elif tool_type == "Cortex Analyst":
                    analyst_type = st.radio(
                        "Analyst Type",
                        ["YAML", "View"],
                        index=0 if tool.get('analyst_type') != 'view' else 1,
                        key=f"analyst_type_{idx}"
                    )
                    tool['analyst_type'] = analyst_type.lower()
                    tool['tool_type'] = 'cortex_analyst_text_to_sql'
                    
                    # Warehouse is required for Cortex Analyst
                    if session:
                        warehouses = get_warehouses(session)
                        if warehouses:
                            current_wh = tool.get('warehouse', '')
                            wh_index = warehouses.index(current_wh) if current_wh in warehouses else 0
                            selected_warehouse = st.selectbox(
                                "Warehouse *",
                                warehouses,
                                index=wh_index,
                                key=f"analyst_warehouse_{idx}"
                            )
                            tool['warehouse'] = selected_warehouse
                        else:
                            # Fallback to text input if we can't query warehouses
                            tool['warehouse'] = st.text_input(
                                "Warehouse *",
                                value=tool.get('warehouse', ''),
                                key=f"analyst_warehouse_{idx}",
                                help="Required: Warehouse name for Cortex Analyst execution"
                            )
                    else:
                        tool['warehouse'] = st.text_input(
                            "Warehouse *",
                            value=tool.get('warehouse', ''),
                            key=f"analyst_warehouse_{idx}",
                            help="Required: Warehouse name for Cortex Analyst execution"
                        )
                    
                    if analyst_type == "YAML":
                        if session and tool.get('database') and tool.get('schema'):
                            stages = get_stages(session, tool['database'], tool['schema'])
                            if stages:
                                # Get current stage from session state or tool dict
                                current_stage = st.session_state.get(f"stage_{idx}", tool.get('stage', ''))
                                stage_index = stages.index(current_stage) if current_stage in stages else 0
                                selected_stage = st.selectbox(
                                    "Stage *",
                                    stages,
                                    index=stage_index,
                                    key=f"stage_{idx}"
                                )
                                
                                # If stage changed, reset yaml_file and rerun
                                if selected_stage != current_stage:
                                    if f"yaml_file_{idx}" in st.session_state:
                                        del st.session_state[f"yaml_file_{idx}"]
                                    st.rerun()
                                
                                # Use the selected stage for building path (selected_stage is the current value)
                                stage_path = f"{tool.get('database', '')}.{tool.get('schema', '')}.{selected_stage}"
                                yaml_files = get_stage_files(session, stage_path)
                                if yaml_files:
                                    # Get current yaml from session state or tool dict
                                    current_yaml = st.session_state.get(f"yaml_file_{idx}", tool.get('yaml_file', ''))
                                    yaml_index = yaml_files.index(current_yaml) if current_yaml in yaml_files else 0
                                    selected_yaml = st.selectbox(
                                        "YAML File *",
                                        yaml_files,
                                        index=yaml_index,
                                        key=f"yaml_file_{idx}"
                                    )
                                else:
                                    st.warning("No YAML files found in selected stage")
                            else:
                                st.warning("No stages found in selected schema")
                    elif analyst_type == "View":
                        if session and tool.get('database') and tool.get('schema'):
                            semantic_views = get_semantic_views(session, tool['database'], tool['schema'])
                            if semantic_views:
                                current_view = tool.get('semantic_view', '')
                                view_index = semantic_views.index(current_view) if current_view in semantic_views else 0
                                selected_view = st.selectbox(
                                    "Semantic View *",
                                    semantic_views,
                                    index=view_index,
                                    key=f"semantic_view_{idx}"
                                )
                                # Don't set directly - let session state handle it
                                # tool['semantic_view'] = selected_view
                            else:
                                st.warning("No semantic views found in selected schema")
                
                elif tool_type == "Custom Tool":
                    custom_type = st.radio(
                        "Custom Type",
                        ["Procedure", "UDF"],
                        index=0 if tool.get('custom_type') != 'udf' else 1,
                        key=f"custom_type_{idx}"
                    )
                    tool['custom_type'] = custom_type.lower()
                    tool['tool_type'] = 'generic'  # Custom tools use 'generic' type
                    
                    # Optional warehouse and query_timeout for custom tools
                    st.write("**Optional Execution Settings:**")
                    col1, col2 = st.columns(2)
                    with col1:
                        if session:
                            warehouses = get_warehouses(session)
                            if warehouses:
                                current_wh = tool.get('warehouse', '')
                                if current_wh and current_wh in warehouses:
                                    warehouse_idx = warehouses.index(current_wh) + 1
                                else:
                                    warehouse_idx = 0
                                selected_wh = st.selectbox(
                                    "Warehouse",
                                    [""] + warehouses,
                                    index=warehouse_idx,
                                    key=f"custom_warehouse_{idx}",
                                    help="Optional: Warehouse for execution"
                                )
                                tool['warehouse'] = selected_wh if selected_wh else ''
                            else:
                                tool['warehouse'] = st.text_input(
                                    "Warehouse",
                                    value=tool.get('warehouse', ''),
                                    key=f"custom_warehouse_{idx}",
                                    help="Optional: Warehouse name"
                                )
                        else:
                            tool['warehouse'] = st.text_input(
                                "Warehouse",
                                value=tool.get('warehouse', ''),
                                key=f"custom_warehouse_{idx}",
                                help="Optional: Warehouse name"
                            )
                    with col2:
                        tool['query_timeout'] = st.number_input(
                            "Query Timeout (seconds)",
                            min_value=1,
                            max_value=3600,
                            value=tool.get('query_timeout', 120),
                            key=f"custom_timeout_{idx}",
                            help="Optional: Query timeout in seconds"
                        )
                    
                    if custom_type == "Procedure":
                        if session and tool.get('database') and tool.get('schema'):
                            procedures = get_procedures(session, tool['database'], tool['schema'])
                            if procedures:
                                selected_proc = st.selectbox(
                                    "Procedure *",
                                    procedures,
                                    index=procedures.index(tool['procedure']) if tool.get('procedure') in procedures else 0,
                                    key=f"custom_proc_{idx}"
                                )
                                tool['procedure'] = selected_proc
                            else:
                                st.warning("No procedures found in selected schema")
                    elif custom_type == "UDF":
                        if session and tool.get('database') and tool.get('schema'):
                            udfs = get_udfs(session, tool['database'], tool['schema'])
                            if udfs:
                                selected_udf = st.selectbox(
                                    "UDF *",
                                    udfs,
                                    index=udfs.index(tool['udf']) if tool.get('udf') in udfs else 0,
                                    key=f"custom_udf_{idx}"
                                )
                                tool['udf'] = selected_udf
                            else:
                                st.warning("No UDFs found in selected schema")
                
                # Update tool in session state from widget values
                # Note: We need to read from session state keys since widgets maintain their own state
                if f"tool_name_{idx}" in st.session_state:
                    tool['tool_name'] = st.session_state[f"tool_name_{idx}"]
                if f"tool_comment_{idx}" in st.session_state:
                    tool['tool_comment'] = st.session_state[f"tool_comment_{idx}"]
                if f"tool_description_{idx}" in st.session_state:
                    tool['tool_description'] = st.session_state[f"tool_description_{idx}"]
                if f"tool_db_{idx}" in st.session_state:
                    tool['database'] = st.session_state[f"tool_db_{idx}"]
                if f"tool_schema_{idx}" in st.session_state:
                    tool['schema'] = st.session_state[f"tool_schema_{idx}"]
                # Note: tool_type is set in the conditional sections above, don't overwrite here
                if f"analyst_type_{idx}" in st.session_state:
                    tool['analyst_type'] = st.session_state[f"analyst_type_{idx}"].lower()
                if f"custom_type_{idx}" in st.session_state:
                    tool['custom_type'] = st.session_state[f"custom_type_{idx}"].lower()
                if f"cortex_search_{idx}" in st.session_state:
                    tool['cortex_search_service'] = st.session_state[f"cortex_search_{idx}"]
                # Always read from session state for these fields (they're set by selectbox)
                if f"stage_{idx}" in st.session_state:
                    tool['stage'] = st.session_state[f"stage_{idx}"]
                else:
                    # If not in session state, keep existing value
                    pass
                if f"yaml_file_{idx}" in st.session_state:
                    tool['yaml_file'] = st.session_state[f"yaml_file_{idx}"]
                else:
                    # If not in session state, keep existing value
                    pass
                if f"semantic_view_{idx}" in st.session_state:
                    tool['semantic_view'] = st.session_state[f"semantic_view_{idx}"]
                else:
                    # If not in session state, keep existing value
                    pass
                if f"custom_view_{idx}" in st.session_state:
                    tool['view'] = st.session_state[f"custom_view_{idx}"]
                if f"custom_proc_{idx}" in st.session_state:
                    tool['procedure'] = st.session_state[f"custom_proc_{idx}"]
                if f"custom_udf_{idx}" in st.session_state:
                    tool['udf'] = st.session_state[f"custom_udf_{idx}"]
                if f"analyst_warehouse_{idx}" in st.session_state:
                    tool['warehouse'] = st.session_state[f"analyst_warehouse_{idx}"]
                if f"custom_warehouse_{idx}" in st.session_state:
                    tool['warehouse'] = st.session_state[f"custom_warehouse_{idx}"]
                if f"custom_timeout_{idx}" in st.session_state:
                    tool['query_timeout'] = st.session_state[f"custom_timeout_{idx}"]
                if f"search_id_col_{idx}" in st.session_state:
                    tool['search_id_column'] = st.session_state[f"search_id_col_{idx}"]
                if f"search_max_{idx}" in st.session_state:
                    tool['search_max_results'] = st.session_state[f"search_max_{idx}"]
                if f"search_title_col_{idx}" in st.session_state:
                    tool['search_title_column'] = st.session_state[f"search_title_col_{idx}"]
                if f"tool_description_{idx}" in st.session_state:
                    tool['tool_description'] = st.session_state[f"tool_description_{idx}"]
                if f"tool_comment_{idx}" in st.session_state:
                    tool['tool_comment'] = st.session_state[f"tool_comment_{idx}"]
    
    st.divider()
    
    # Step 2: Basic Information (SECOND)
    st.subheader("Step 2: Basic Information")
    with st.form("create_agent_form"):
        agent_name = st.text_input("Agent Name *", placeholder="MY_NEW_AGENT", help="Required: Name of the agent")
        comment = st.text_area("Comment", placeholder="Description of the agent")
        display_name = st.text_input("Display Name", placeholder="My New Agent")
        
        st.divider()
        st.subheader("Instructions")
        orchestration_instructions = st.text_area(
            "Orchestration Instructions",
            placeholder="How should the agent orchestrate tasks?",
            help="Instructions for how the agent should orchestrate its tools"
        )
        response_instructions = st.text_area(
            "Response Instructions",
            placeholder="How should the agent respond to users?",
            help="Instructions for how the agent should format its responses"
        )
        
        st.divider()
        st.subheader("Model Configuration")
        orchestration_model = st.selectbox(
            "Orchestration Model",
            ["claude-4-sonnet", "llama3.1-70B", "auto"],
            index=2,
            help="Model to use for orchestration. 'auto' lets Snowflake choose."
        )
        
        st.divider()
        st.subheader("Budget Constraints")
        col1, col2 = st.columns(2)
        with col1:
            time_budget = st.number_input("Time Budget (seconds) *", min_value=1, max_value=300, value=30, help="Required: Maximum execution time in seconds")
        with col2:
            token_budget = st.number_input("Token Budget *", min_value=1000, max_value=100000, value=16000, help="Required: Maximum tokens to use")
        
        # Form submit buttons
        col1, col2 = st.columns(2)
        with col1:
            generate_sql = st.form_submit_button("📋 Generate SQL", type="primary")
        with col2:
            create_agent = st.form_submit_button("🚀 Create Agent", type="primary")
        
        if generate_sql or create_agent:
            # Validate required fields
            if not agent_name:
                st.error("❌ Agent Name is required")
                st.stop()
            
            if not orchestration_instructions and not response_instructions:
                st.warning("⚠️ At least one instruction field is recommended")
            
            # Validate tools - first update all tool values from session state
            for idx, tool in enumerate(st.session_state.tools):
                # Update tool values from session state before validation
                if f"tool_name_{idx}" in st.session_state:
                    tool['tool_name'] = st.session_state[f"tool_name_{idx}"]
                if f"tool_db_{idx}" in st.session_state:
                    tool['database'] = st.session_state[f"tool_db_{idx}"]
                if f"tool_schema_{idx}" in st.session_state:
                    tool['schema'] = st.session_state[f"tool_schema_{idx}"]
                if f"analyst_type_{idx}" in st.session_state:
                    tool['analyst_type'] = st.session_state[f"analyst_type_{idx}"].lower()
                if f"analyst_warehouse_{idx}" in st.session_state:
                    tool['warehouse'] = st.session_state[f"analyst_warehouse_{idx}"]
                if f"stage_{idx}" in st.session_state:
                    tool['stage'] = st.session_state[f"stage_{idx}"]
                if f"yaml_file_{idx}" in st.session_state:
                    tool['yaml_file'] = st.session_state[f"yaml_file_{idx}"]
                if f"semantic_view_{idx}" in st.session_state:
                    tool['semantic_view'] = st.session_state[f"semantic_view_{idx}"]
                if f"cortex_search_{idx}" in st.session_state:
                    tool['cortex_search_service'] = st.session_state[f"cortex_search_{idx}"]
                if f"custom_view_{idx}" in st.session_state:
                    tool['view'] = st.session_state[f"custom_view_{idx}"]
                if f"custom_proc_{idx}" in st.session_state:
                    tool['procedure'] = st.session_state[f"custom_proc_{idx}"]
                if f"custom_udf_{idx}" in st.session_state:
                    tool['udf'] = st.session_state[f"custom_udf_{idx}"]
            
            # Now validate tools
            valid_tools = []
            for idx, tool in enumerate(st.session_state.tools):
                if not tool.get('tool_name') or not tool.get('tool_description'):
                    st.error(f"❌ Tool {idx + 1}: Tool Name and Description are required")
                    continue
                
                # Validate tool-specific requirements
                if tool.get('tool_type') == 'cortex_search':
                    if not tool.get('cortex_search_service'):
                        st.error(f"❌ Tool {idx + 1}: Cortex Search Service is required")
                        continue
                    if not tool.get('database') or not tool.get('schema'):
                        st.error(f"❌ Tool {idx + 1}: Database and Schema are required for Cortex Search")
                        continue
                elif tool.get('tool_type') == 'cortex_analyst_text_to_sql':
                    if not tool.get('warehouse'):
                        st.error(f"❌ Tool {idx + 1}: Warehouse is required for Cortex Analyst")
                        continue
                    if not tool.get('database') or not tool.get('schema'):
                        st.error(f"❌ Tool {idx + 1}: Database and Schema are required for Cortex Analyst")
                        continue
                    if tool.get('analyst_type') == 'yaml':
                        stage_val = tool.get('stage', '')
                        yaml_val = tool.get('yaml_file', '')
                        if not stage_val or not yaml_val:
                            st.error(f"❌ Tool {idx + 1}: Stage and YAML File are required for YAML analyst. Stage: '{stage_val}', YAML: '{yaml_val}'")
                            continue
                    elif tool.get('analyst_type') == 'view':
                        semantic_view_val = tool.get('semantic_view', '')
                        if not semantic_view_val:
                            st.error(f"❌ Tool {idx + 1}: Semantic View is required for View analyst. Current value: '{semantic_view_val}'")
                            continue
                elif tool.get('tool_type') == 'generic':
                    if tool.get('custom_type') == 'procedure' and not tool.get('procedure'):
                        st.error(f"❌ Tool {idx + 1}: Procedure is required for custom procedure tool")
                        continue
                    elif tool.get('custom_type') == 'udf' and not tool.get('udf'):
                        st.error(f"❌ Tool {idx + 1}: UDF is required for custom UDF tool")
                        continue
                    if not tool.get('database') or not tool.get('schema'):
                        st.error(f"❌ Tool {idx + 1}: Database and Schema are required for Custom Tool")
                        continue
                
                valid_tools.append(tool)
            
            if generate_sql or create_agent:
                # Build agent configuration
                agent_config = build_agent_config(
                    agent_name=agent_name,
                    comment=comment,
                    display_name=display_name,
                    orchestration_instructions=orchestration_instructions,
                    response_instructions=response_instructions,
                    orchestration_model=orchestration_model,
                    time_budget=time_budget,
                    token_budget=token_budget,
                    tools=valid_tools,
                    target_database=st.session_state.selected_database,
                    target_schema=st.session_state.selected_schema
                )
                
                # Generate SQL
                sql_statement = generate_agent_sql_from_config(
                    agent_name=agent_name,
                    database=st.session_state.selected_database,
                    schema=st.session_state.selected_schema,
                    agent_config=agent_config,
                    comment=comment
                )
                
                # Store SQL in session state to display outside form
                if generate_sql:
                    st.session_state.generated_sql = sql_statement
                    st.session_state.sql_agent_name = agent_name
                    st.rerun()
                
                if create_agent:
                    if not target_client:
                        st.error("❌ Target account not configured. Please update your env.dev file.")
                    else:
                        with st.spinner("Creating agent..."):
                            success = target_client.create_agent(
                                st.session_state.selected_database,
                                st.session_state.selected_schema,
                                agent_config
                            )
                            
                            if success:
                                st.session_state.generated_sql = sql_statement
                                st.session_state.sql_agent_name = agent_name
                                st.success(f"✅ Agent '{agent_name}' created successfully!")
                                st.balloons()
                                st.rerun()
                            else:
                                st.error("❌ Failed to create agent. Check the logs for details.")
                else:
                    st.warning("Please enter an agent name")
    
    # Display generated SQL outside the form (if available)
    if st.session_state.generated_sql:
        st.divider()
        st.subheader("📋 Generated SQL")
        st.code(st.session_state.generated_sql, language='sql')
        st.download_button(
            label="📥 Download SQL",
            data=st.session_state.generated_sql,
            file_name=f"{st.session_state.sql_agent_name}_create_agent.sql",
            mime="text/plain"
        )
        if st.button("🗑️ Clear SQL", type="secondary"):
            st.session_state.generated_sql = None
            st.session_state.sql_agent_name = ''
            st.rerun()

if __name__ == "__main__":
    main()

