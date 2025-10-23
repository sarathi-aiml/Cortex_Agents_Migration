import streamlit as st
import json
from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime
from snowflake.snowpark import Session

# Initialize Snowflake session for Streamlit-in-Snowflake
@st.cache_resource
def get_session():
    """Get the active Snowflake session"""
    return Session.builder.getOrCreate()

def truncate_description(description: str, max_length: int = 200) -> str:
    """Truncate overly long descriptions to make them more concise"""
    if not description:
        return ""
    
    # If description is short enough, return as is
    if len(description) <= max_length:
        return description
    
    # Find the last complete sentence within the limit
    truncated = description[:max_length]
    last_period = truncated.rfind('.')
    last_newline = truncated.rfind('\n')
    
    # Use the last complete sentence or line
    if last_period > max_length * 0.7:  # If we have a good sentence break
        return description[:last_period + 1]
    elif last_newline > max_length * 0.7:  # If we have a good line break
        return description[:last_newline]
    else:
        # Just truncate and add ellipsis
        return description[:max_length - 3] + "..."

def generate_agent_sql(agent_name: str, database: str, schema: str, agent_spec_str: str, comment: str = '') -> str:
    """Convert agent JSON specification to SQL CREATE AGENT statement"""
    try:
        agent_spec = json.loads(agent_spec_str)
    except json.JSONDecodeError as e:
        return f"-- Error: Invalid JSON specification - {str(e)}"
    
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
        
        # Handle system
        if 'system' in instructions and instructions['system']:
            yaml_content.append(f'  system: "{instructions["system"]}"')
        
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
                
                # Handle description - use quotes for short descriptions, pipe for long ones
                desc = tool_spec.get('description', '')
                if desc:
                    # Truncate overly long descriptions
                    desc = truncate_description(desc, 300)
                    
                    # If description is very long (>200 chars) or has multiple lines, use pipe
                    if len(desc) > 200 or '\n' in desc:
                        yaml_content.append("      description: |")
                        # Split by newlines if they exist
                        for line in desc.split('\n'):
                            yaml_content.append(f"        {line}")
                    else:
                        # Use quotes for shorter descriptions
                        yaml_content.append(f'      description: "{desc}"')
                
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
                                # Truncate overly long descriptions
                                desc = truncate_description(desc, 150)
                                
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
            
            # Handle other resource fields in specific order based on tool type
            tool_type = resources.get('type', '')
            
            if tool_type == 'function':
                # For function tools: identifier, name, type
                field_order = ['identifier', 'name', 'type']
            elif tool_type == 'procedure':
                # For procedure tools: identifier, name, type  
                field_order = ['identifier', 'name', 'type']
            elif 'semantic_model_file' in resources:
                # For cortex_analyst tools: semantic_model_file
                field_order = ['semantic_model_file']
            elif 'id_column' in resources:
                # For cortex_search tools: id_column, max_results, name, title_column
                field_order = ['id_column', 'max_results', 'name', 'title_column']
            else:
                # Default order
                field_order = ['identifier', 'name', 'type', 'semantic_model_file', 'id_column', 'max_results', 'title_column', 'search_service', 'filter']
            
            for field in field_order:
                if field in resources and field != 'execution_environment':
                    resource_value = resources[field]
                    if isinstance(resource_value, str):
                        yaml_content.append(f'    {field}: "{resource_value}"')
                    elif isinstance(resource_value, int):
                        yaml_content.append(f"    {field}: {resource_value}")
                    elif isinstance(resource_value, dict):
                        # Handle complex objects like filter
                        yaml_content.append(f"    {field}:")
                        for k, v in resource_value.items():
                            if isinstance(v, dict):
                                yaml_content.append(f"      {k}:")
                                for sub_k, sub_v in v.items():
                                    yaml_content.append(f"        {sub_k}: \"{sub_v}\"")
                            else:
                                yaml_content.append(f"      {k}: \"{v}\"")
            
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
    
    # Handle profile
    if 'profile' in agent_spec and agent_spec['profile']:
        yaml_content.append("profile:")
        for profile_key, profile_value in agent_spec['profile'].items():
            if profile_value:
                yaml_content.append(f'  {profile_key}: "{profile_value}"')
    
    # Combine all parts
    sql_parts.append('\n'.join(yaml_content))
    sql_parts.append("$$;")
    
    return '\n'.join(sql_parts)

def get_databases(session) -> List[str]:
    """Get list of databases accessible to the current session"""
    try:
        result = session.sql("SHOW DATABASES").collect()
        databases = [row['name'] for row in result if row['name'] not in ['INFORMATION_SCHEMA']]
        return databases
    except Exception as e:
        st.error(f"Error fetching databases: {str(e)}")
        return []

def get_schemas(session, database: str) -> List[str]:
    """Get list of schemas in the specified database"""
    try:
        result = session.sql(f"SHOW SCHEMAS IN DATABASE {database}").collect()
        schemas = [row['name'] for row in result if row['name'] not in ['INFORMATION_SCHEMA']]
        return schemas
    except Exception as e:
        st.error(f"Error fetching schemas: {str(e)}")
        return []

def get_agents(session, database: str, schema: str) -> List[Dict]:
    """Get list of agents in the specified database and schema"""
    try:
        result = session.sql(f"SHOW AGENTS IN SCHEMA {database}.{schema}").collect()
        agents = []
        
        for row in result:
            # Convert row to dict for easier access
            if hasattr(row, 'asDict'):
                row_dict = row.asDict()
            else:
                # Fallback: try to access columns directly
                row_dict = {}
                try:
                    row_dict['name'] = row['name']
                    row_dict['comment'] = getattr(row, 'comment', '')
                    row_dict['created_on'] = getattr(row, 'created_on', '')
                    row_dict['owner'] = getattr(row, 'owner', '')
                except (KeyError, AttributeError) as e:
                    continue
            
            agents.append({
                'name': row_dict.get('name') or '',
                'comment': row_dict.get('comment') or '',
                'created_on': row_dict.get('created_on') or '',
                'owner': row_dict.get('owner') or ''
            })
        return agents
    except Exception as e:
        st.error(f"Error fetching agents: {str(e)}")
        return []

def get_agent_details(session, database: str, schema: str, agent_name: str) -> Optional[Dict]:
    """Get detailed information about a specific agent"""
    try:
        # First try DESCRIBE AGENT
        result = session.sql(f"DESCRIBE AGENT {database}.{schema}.{agent_name}").collect()
        if result:
            # Convert row to dict for easier access
            row_dict = result[0].asDict() if hasattr(result[0], 'asDict') else dict(result[0])
            
            # Try different possible column names for specification
            agent_spec = None
            for spec_key in ['agent_spec', 'AGENT_SPEC', 'specification', 'SPECIFICATION', 'spec', 'SPEC', 'definition', 'DEFINITION']:
                if spec_key in row_dict and row_dict[spec_key]:
                    agent_spec = row_dict[spec_key]
                    break
            
            return {
                'name': agent_name,
                'specification': agent_spec or '{}',
                'comment': row_dict.get('comment') or '',
                'created_on': row_dict.get('created_on') or '',
                'owner': row_dict.get('owner') or ''
            }
        return None
    except Exception as e:
        st.error(f"Error fetching agent details: {str(e)}")
        return None

def main():
    st.set_page_config(
        page_title="Snowflake Cortex Agent SQL Generator",
        page_icon="🔧",
        layout="wide"
    )
    
    st.title("🔧 Snowflake Cortex Agent SQL Generator")
    st.markdown("Generate SQL CREATE AGENT statements from existing agents")
    
    # Get Snowflake session info first
    try:
        session = get_session()
        current_database = session.get_current_database()
        current_schema = session.get_current_schema()
    except Exception as e:
        st.error(f"Error connecting to Snowflake: {str(e)}")
        st.stop()
    
    # Initialize session state
    if 'generated_sql' not in st.session_state:
        st.session_state.generated_sql = ""
    if 'selected_database' not in st.session_state:
        st.session_state.selected_database = current_database
    if 'selected_schema' not in st.session_state:
        st.session_state.selected_schema = current_schema
    if 'available_agents' not in st.session_state:
        st.session_state.available_agents = []
    if 'selected_agent_details' not in st.session_state:
        st.session_state.selected_agent_details = None
    
    # Simple, clean interface
    st.write("**Step 1: Select Database and Schema**")
    col1, col2 = st.columns(2)
    
    with col1:
        databases = get_databases(session)
        if databases:
            selected_db = st.selectbox(
                "Select Database:",
                databases,
                index=databases.index(st.session_state.selected_database) if st.session_state.selected_database in databases else 0,
                key="db_selector"
            )
            if selected_db != st.session_state.selected_database:
                st.session_state.selected_database = selected_db
                st.session_state.selected_schema = None
                st.session_state.available_agents = []
                st.session_state.selected_agent_details = None
                st.rerun()
    
    with col2:
        if st.session_state.selected_database:
            schemas = get_schemas(session, st.session_state.selected_database)
            if schemas:
                selected_schema = st.selectbox(
                    "Select Schema:",
                    schemas,
                    index=schemas.index(st.session_state.selected_schema) if st.session_state.selected_schema in schemas else 0,
                    key="schema_selector"
                )
                if selected_schema != st.session_state.selected_schema:
                    st.session_state.selected_schema = selected_schema
                    st.session_state.available_agents = []
                    st.session_state.selected_agent_details = None
                    st.rerun()
    
    # Step 2: Load Agents
    if st.session_state.selected_database and st.session_state.selected_schema:
        st.write("**Step 2: Load Available Agents**")
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.write(f"Loading agents from **{st.session_state.selected_database}.{st.session_state.selected_schema}**")
        
        with col2:
            if st.button("🔄 Load Agents", type="primary"):
                with st.spinner("Loading agents..."):
                    agents = get_agents(session, st.session_state.selected_database, st.session_state.selected_schema)
                    st.session_state.available_agents = agents
                    if agents:
                        st.success(f"Found {len(agents)} agent(s)")
                    else:
                        st.warning("No agents found or error occurred")
                        st.session_state.available_agents = []
        
        # Display agents if available
        if st.session_state.available_agents:
            st.write("**Step 3: Select Agent**")
            agent_data = []
            for agent in st.session_state.available_agents:
                comment = agent.get('comment') or ''
                created = agent.get('created_on') or 'N/A'
                owner = agent.get('owner') or 'N/A'
                
                agent_data.append({
                    'Name': agent.get('name', 'N/A'),
                    'Comment': comment,
                    'Created': created,
                    'Owner': owner
                })
            
            df = pd.DataFrame(agent_data)
            st.dataframe(df, use_container_width=True)
            
            # Agent selection
            agent_names = [agent['name'] for agent in st.session_state.available_agents]
            selected_agent_name = st.selectbox(
                "Select Agent to Generate SQL:",
                agent_names,
                help="Choose the agent you want to generate SQL for"
            )
            
            if selected_agent_name:
                # Load agent details button
                if st.button("📥 Load Agent Details", type="secondary"):
                    with st.spinner("Loading agent details..."):
                        agent_details = get_agent_details(
                            session, 
                            st.session_state.selected_database, 
                            st.session_state.selected_schema, 
                            selected_agent_name
                        )
                        
                        if agent_details:
                            st.session_state.selected_agent_details = agent_details
                            st.success(f"Loaded details for agent: {selected_agent_name}")
                        else:
                            st.error(f"Failed to load details for agent: {selected_agent_name}")
                
                # Display agent details and generate SQL
                if st.session_state.selected_agent_details:
                    st.write("**Step 4: Review Agent Configuration**")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Name:** {st.session_state.selected_agent_details.get('name', 'N/A')}")
                        st.write(f"**Comment:** {st.session_state.selected_agent_details.get('comment', 'N/A')}")
                    with col2:
                        st.write(f"**Created:** {st.session_state.selected_agent_details.get('created_on', 'N/A')}")
                        st.write(f"**Owner:** {st.session_state.selected_agent_details.get('owner', 'N/A')}")
                    
                    # Generate SQL for existing agent
                    if st.button("🔧 Generate SQL", type="primary"):
                        agent_spec = st.session_state.selected_agent_details.get('specification', '{}')
                        agent_comment = st.session_state.selected_agent_details.get('comment', '')
                        
                        # Generate SQL
                        sql_statement = generate_agent_sql(
                            agent_name=selected_agent_name,
                            database=st.session_state.selected_database,
                            schema=st.session_state.selected_schema,
                            agent_spec_str=agent_spec,
                            comment=agent_comment
                        )
                        
                        st.session_state.generated_sql = sql_statement
                        st.success("✅ SQL generated successfully!")
                    
                    # Show agent specification
                    with st.expander("🔧 Agent Specification"):
                        agent_spec = st.session_state.selected_agent_details.get('specification', '{}')
                        try:
                            formatted_spec = json.loads(agent_spec)
                            st.json(formatted_spec)
                        except json.JSONDecodeError:
                            st.text(agent_spec)
        else:
            st.info("👆 Select database and schema, then click 'Load Agents' to see available agents")
    
    # Display generated SQL
    if st.session_state.generated_sql:
        st.divider()
        st.write("**Generated SQL Statement**")
        
        st.code(st.session_state.generated_sql, language='sql')
        
        # Download button
        sql_bytes = st.session_state.generated_sql.encode('utf-8')
        st.download_button(
            label="💾 Download SQL",
            data=sql_bytes,
            file_name=f"create_agent_{st.session_state.selected_agent_details.get('name', 'agent') if st.session_state.selected_agent_details else 'agent'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql",
            mime="text/sql"
        )

if __name__ == "__main__":
    main()