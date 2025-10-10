import streamlit as st
import requests
import json
import os
from typing import Dict, List, Optional, Tuple
import pandas as pd
from datetime import datetime

# Load environment variables
def load_env():
    """Load environment variables from env.dev file"""
    env_vars = {}
    try:
        with open('env.dev', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value
    except FileNotFoundError:
        st.error("env.dev file not found. Please ensure it exists in the current directory.")
        return None
    return env_vars

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
    
    def list_agents(self, database: str, schema: str) -> List[Dict]:
        """List all agents in the specified database and schema"""
        url = f"{self.base_url}/databases/{database}/schemas/{schema}/agents"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            st.error(f"Error listing agents from {self.account_name}: {str(e)}")
            return []
    
    def get_agent_details(self, database: str, schema: str, agent_name: str) -> Optional[Dict]:
        """Get detailed information about a specific agent"""
        url = f"{self.base_url}/databases/{database}/schemas/{schema}/agents/{agent_name}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            st.error(f"Error getting agent details from {self.account_name}: {str(e)}")
            return None
    
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

def format_agent_spec(agent_spec: str) -> Dict:
    """Parse and format the agent specification JSON"""
    try:
        return json.loads(agent_spec)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON format"}

def display_agent_profile(profile: Dict):
    """Display agent profile information"""
    if not profile:
        return
    
    st.subheader("👤 Agent Profile")
    col1, col2 = st.columns(2)
    
    with col1:
        if 'display_name' in profile:
            st.write(f"**Display Name:** {profile['display_name']}")
        if 'avatar' in profile:
            st.write(f"**Avatar:** {profile['avatar']}")
    
    with col2:
        if 'color' in profile:
            st.write(f"**Color:** {profile['color']}")

def display_agent_instructions(instructions: Dict):
    """Display agent instructions"""
    if not instructions:
        return
    
    st.subheader("📋 Instructions")
    
    if 'response' in instructions:
        st.write("**Response Instructions:**")
        st.write(instructions['response'])
    
    if 'orchestration' in instructions:
        st.write("**Orchestration Instructions:**")
        st.write(instructions['orchestration'])
    
    if 'system' in instructions:
        st.write("**System Instructions:**")
        st.write(instructions['system'])
    
    if 'sample_questions' in instructions and instructions['sample_questions']:
        st.write("**Sample Questions:**")
        for i, question in enumerate(instructions['sample_questions'], 1):
            st.write(f"{i}. {question.get('question', 'N/A')}")

def display_agent_tools(tools: List[Dict]):
    """Display agent tools"""
    if not tools:
        return
    
    st.subheader("🔧 Tools")
    
    for i, tool in enumerate(tools, 1):
        with st.expander(f"Tool {i}: {tool.get('tool_spec', {}).get('name', 'Unnamed')}"):
            tool_spec = tool.get('tool_spec', {})
            
            st.write(f"**Type:** {tool_spec.get('type', 'N/A')}")
            st.write(f"**Description:** {tool_spec.get('description', 'N/A')}")
            
            if 'input_schema' in tool_spec:
                st.write("**Input Schema:**")
                st.json(tool_spec['input_schema'])

def display_agent_models(models: Dict):
    """Display agent model configuration"""
    if not models:
        return
    
    st.subheader("🤖 Model Configuration")
    
    if 'orchestration' in models:
        st.write(f"**Orchestration Model:** {models['orchestration']}")

def display_agent_orchestration(orchestration: Dict):
    """Display orchestration configuration"""
    if not orchestration:
        return
    
    st.subheader("⚙️ Orchestration Configuration")
    
    if 'budget' in orchestration:
        budget = orchestration['budget']
        st.write("**Budget Constraints:**")
        if 'seconds' in budget:
            st.write(f"- Time Limit: {budget['seconds']} seconds")
        if 'tokens' in budget:
            st.write(f"- Token Limit: {budget['tokens']} tokens")

def main():
    st.set_page_config(
        page_title="Snowflake Cortex Agent Cross-Account Migration Tool",
        page_icon="🔄",
        layout="wide"
    )
    
    st.title("🔄 Snowflake Cortex Agent Cross-Account Migration Tool")
    st.markdown("Migrate Cortex Agents between different Snowflake accounts and environments")
    
    # Initialize session state
    if 'migration_history' not in st.session_state:
        st.session_state.migration_history = []
    if 'source_agents' not in st.session_state:
        st.session_state.source_agents = []
    if 'selected_agent_details' not in st.session_state:
        st.session_state.selected_agent_details = None
    
    # Load environment variables
    env_vars = load_env()
    if not env_vars:
        st.stop()
    
    # Extract configuration
    source_config = {
        'url': env_vars.get('SOURCE_ACCOUNT_URL', ''),
        'pat': env_vars.get('SOURCE_PAT', ''),
        'database': env_vars.get('SOURCE_DATABASE', ''),
        'schema': env_vars.get('SOURCE_SCHEMA', ''),
        'default_agent': env_vars.get('SOURCE_DEFAULT_AGENT', '')
    }
    
    target_config = {
        'url': env_vars.get('TARGET_ACCOUNT_URL', ''),
        'pat': env_vars.get('TARGET_PAT', ''),
        'database': env_vars.get('TARGET_DATABASE', ''),
        'schema': env_vars.get('TARGET_SCHEMA', '')
    }
    
    migration_settings = {
        'suffix': env_vars.get('MIGRATION_NAME_SUFFIX', '_PROD'),
        'add_metadata': env_vars.get('ADD_MIGRATION_METADATA', 'true').lower() == 'true',
        'test_connections': env_vars.get('TEST_CONNECTIONS', 'true').lower() == 'true'
    }
    
    # Initialize API clients
    source_client = None
    target_client = None
    
    if source_config['url'] and source_config['pat']:
        source_client = SnowflakeCortexAgentAPI(
            account_url=source_config['url'],
            pat_token=source_config['pat'],
            account_name="Source (DEV)"
        )
    
    if target_config['url'] and target_config['pat']:
        target_client = SnowflakeCortexAgentAPI(
            account_url=target_config['url'],
            pat_token=target_config['pat'],
            account_name="Target (PROD)"
        )
    
    # Sidebar for account information
    with st.sidebar:
        st.header("🌐 Account Configuration")
        
        # Source Account Info
        st.subheader("📥 Source Account (DEV)")
        if source_config['url']:
            st.write(f"**URL:** {source_config['url']}")
            st.write(f"**Database:** {source_config['database']}")
            st.write(f"**Schema:** {source_config['schema']}")
        else:
            st.error("Source account not configured")
        
        st.divider()
        
        # Target Account Info
        st.subheader("📤 Target Account (PROD)")
        if target_config['url'] and target_config['url'] != 'https://<TARGET_ACCOUNT>.snowflakecomputing.com':
            st.write(f"**URL:** {target_config['url']}")
            st.write(f"**Database:** {target_config['database']}")
            st.write(f"**Schema:** {target_config['schema']}")
        else:
            st.warning("Target account not configured")
        
        st.divider()
        
        # Connection Test
        if migration_settings['test_connections']:
            st.subheader("🔗 Connection Test")
            
            if source_client:
                if st.button("Test Source Connection", type="secondary"):
                    with st.spinner("Testing source connection..."):
                        success, message = source_client.test_connection()
                        if success:
                            st.success("✅ Source connection OK")
                        else:
                            st.error(f"❌ Source connection failed: {message}")
            
            if target_client:
                if st.button("Test Target Connection", type="secondary"):
                    with st.spinner("Testing target connection..."):
                        success, message = target_client.test_connection()
                        if success:
                            st.success("✅ Target connection OK")
                        else:
                            st.error(f"❌ Target connection failed: {message}")
    
    # Main content area
    tab1, tab2, tab3, tab4 = st.tabs(["🚀 Migration", "📋 Agent Details", "➕ Create Agent", "📊 Migration History"])
    
    with tab1:
        st.header("🚀 Cross-Account Agent Migration")
        
        if not source_client:
            st.error("❌ Source account not configured. Please update your env.dev file.")
            st.stop()
        
        if not target_client:
            st.error("❌ Target account not configured. Please update your env.dev file.")
            st.stop()
        
        # Step 1: Load Source Agents
        st.subheader("📥 Step 1: Load Source Agents")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"Loading agents from **{source_config['database']}.{source_config['schema']}**")
        with col2:
            if st.button("🔄 Refresh Agent List", type="primary"):
                with st.spinner("Loading agents from source account..."):
                    agents = source_client.list_agents(source_config['database'], source_config['schema'])
                    
                    if agents:
                        st.session_state.source_agents = agents
                        st.success(f"Found {len(agents)} agent(s)")
                    else:
                        st.warning("No agents found or error occurred")
                        st.session_state.source_agents = []
        
        # Display agents if available
        if st.session_state.source_agents:
            agent_data = []
            for agent in st.session_state.source_agents:
                agent_data.append({
                    'Name': agent.get('name', 'N/A'),
                    'Comment': agent.get('comment', 'N/A'),
                    'Created': agent.get('created_on', 'N/A'),
                    'Owner': agent.get('owner', 'N/A')
                })
            
            df = pd.DataFrame(agent_data)
            st.dataframe(df, use_container_width=True)
        
        # Step 2: Select Agent for Migration
        if st.session_state.source_agents:
            st.divider()
            st.subheader("🎯 Step 2: Select Agent for Migration")
            
            agent_names = [agent.get('name', 'N/A') for agent in st.session_state.source_agents]
            selected_agent_name = st.selectbox(
                "Select Agent to Migrate:",
                agent_names,
                help="Choose the agent you want to migrate to the target account"
            )
            
            if selected_agent_name and selected_agent_name != 'N/A':
                # Load agent details
                if st.button("📥 Load Agent Details", type="secondary"):
                    with st.spinner("Loading agent details..."):
                        agent_details = source_client.get_agent_details(
                            source_config['database'], 
                            source_config['schema'], 
                            selected_agent_name
                        )
                        
                        if agent_details:
                            st.session_state.selected_agent_details = agent_details
                            st.success(f"Loaded details for agent: {selected_agent_name}")
                        else:
                            st.error(f"Failed to load details for agent: {selected_agent_name}")
                
                # Step 3: Review Agent Configuration
                if st.session_state.selected_agent_details:
                    st.divider()
                    st.subheader("📄 Step 3: Review Agent Configuration")
                    
                    agent_spec = st.session_state.selected_agent_details.get('agent_spec', '{}')
                    
                    # Display raw agent specification
                    st.text_area(
                        "Full Agent Specification (JSON):",
                        value=agent_spec,
                        height=300,
                        help="This is the complete agent specification that will be migrated"
                    )
                    
                    # Step 4: Configure Migration
                    st.divider()
                    st.subheader("⚙️ Step 4: Configure Migration")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Target Configuration:**")
                        st.write(f"Account: {target_config['url']}")
                        st.write(f"Database: {target_config['database']}")
                        st.write(f"Schema: {target_config['schema']}")
                    
                    with col2:
                        st.write("**Migration Options:**")
                        
                        # Agent naming options
                        naming_option = st.radio(
                            "Agent Naming:",
                            ["Keep Original Name", "Add Suffix", "Custom Name"],
                            help="Choose how to name the agent in the target environment"
                        )
                        
                        final_agent_name = selected_agent_name
                        if naming_option == "Add Suffix":
                            final_agent_name = f"{selected_agent_name}{migration_settings['suffix']}"
                        elif naming_option == "Custom Name":
                            custom_name = st.text_input("Custom Agent Name:", placeholder=f"{selected_agent_name}_PROD")
                            if custom_name:
                                final_agent_name = custom_name
                    
                    # Step 5: Execute Migration
                    st.divider()
                    st.subheader("🚀 Step 5: Execute Migration")
                    
                    # Migration summary
                    st.info(f"""
                    **Migration Summary:**
                    - **Source:** {source_config['url']} → {source_config['database']}.{source_config['schema']}.{selected_agent_name}
                    - **Target:** {target_config['url']} → {target_config['database']}.{target_config['schema']}.{final_agent_name}
                    - **Migration Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    """)
                    
                    # Execute migration
                    if st.button("🚀 Execute Migration", type="primary"):
                        try:
                            agent_spec_json = json.loads(agent_spec)
                            
                            # Prepare migration configuration
                            migration_config = {
                                "name": final_agent_name,
                                **agent_spec_json
                            }
                            
                            # Add migration metadata if enabled
                            if migration_settings['add_metadata']:
                                original_comment = agent_spec_json.get('comment', '')
                                migration_comment = f"{original_comment}\n\n[MIGRATED] From: {source_config['url']} → {source_config['database']}.{source_config['schema']}.{selected_agent_name} on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                                migration_config['comment'] = migration_comment
                            
                            # Execute migration
                            with st.spinner(f"Migrating agent '{final_agent_name}' to target account..."):
                                success = target_client.create_agent(
                                    target_config['database'], 
                                    target_config['schema'], 
                                    migration_config
                                )
                                
                                if success:
                                    st.success(f"✅ Agent '{final_agent_name}' successfully migrated!")
                                    st.balloons()
                                    
                                    # Record migration in history
                                    migration_record = {
                                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        'source_account': source_config['url'],
                                        'source_agent': selected_agent_name,
                                        'source_db': source_config['database'],
                                        'source_schema': source_config['schema'],
                                        'target_account': target_config['url'],
                                        'target_db': target_config['database'],
                                        'target_schema': target_config['schema'],
                                        'target_agent': final_agent_name,
                                        'status': 'Success'
                                    }
                                    st.session_state.migration_history.append(migration_record)
                                    
                                    # Show detailed success message
                                    st.info(f"""
                                    **Migration Completed Successfully!**
                                    
                                    **Source:** {source_config['url']}
                                    - Database: {source_config['database']}
                                    - Schema: {source_config['schema']}
                                    - Agent: {selected_agent_name}
                                    
                                    **Target:** {target_config['url']}
                                    - Database: {target_config['database']}
                                    - Schema: {target_config['schema']}
                                    - Agent: {final_agent_name}
                                    
                                    **Status:** ✅ Successfully Deployed
                                    **Timestamp:** {migration_record['timestamp']}
                                    """)
                                else:
                                    st.error(f"❌ Failed to migrate agent '{final_agent_name}'")
                                    
                                    # Record failed migration
                                    migration_record = {
                                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        'source_account': source_config['url'],
                                        'source_agent': selected_agent_name,
                                        'source_db': source_config['database'],
                                        'source_schema': source_config['schema'],
                                        'target_account': target_config['url'],
                                        'target_db': target_config['database'],
                                        'target_schema': target_config['schema'],
                                        'target_agent': final_agent_name,
                                        'status': 'Failed'
                                    }
                                    st.session_state.migration_history.append(migration_record)
                                    
                        except json.JSONDecodeError as e:
                            st.error(f"Error parsing agent specification: {str(e)}")
                        except Exception as e:
                            st.error(f"Unexpected error during migration: {str(e)}")
        
        else:
            st.info("👆 Click 'Refresh Agent List' to load agents from the source account")
    
    with tab2:
        st.header("🔍 Agent Details")
        
        if not source_client:
            st.error("Source account not configured")
            st.stop()
        
        # Agent selection
        agent_name = st.text_input("Agent Name", value=source_config['default_agent'])
        
        if st.button("🔍 Get Agent Details", type="primary"):
            if agent_name:
                with st.spinner("Loading agent details..."):
                    agent_details = source_client.get_agent_details(
                        source_config['database'], 
                        source_config['schema'], 
                        agent_name
                    )
                    
                    if agent_details:
                        st.success(f"Successfully loaded details for agent: {agent_name}")
                        
                        # Display basic information
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Name:** {agent_details.get('name', 'N/A')}")
                            st.write(f"**Comment:** {agent_details.get('comment', 'N/A')}")
                        with col2:
                            st.write(f"**Created:** {agent_details.get('created_on', 'N/A')}")
                            st.write(f"**Owner:** {agent_details.get('owner', 'N/A')}")
                        
                        # Parse and display agent specification
                        agent_spec_str = agent_details.get('agent_spec', '{}')
                        agent_spec = format_agent_spec(agent_spec_str)
                        
                        if 'error' not in agent_spec:
                            # Display different sections
                            display_agent_profile(agent_spec.get('profile', {}))
                            display_agent_instructions(agent_spec.get('instructions', {}))
                            display_agent_models(agent_spec.get('models', {}))
                            display_agent_orchestration(agent_spec.get('orchestration', {}))
                            display_agent_tools(agent_spec.get('tools', []))
                            
                            # Display raw JSON for debugging
                            with st.expander("🔧 Raw Agent Specification"):
                                st.json(agent_spec)
                        else:
                            st.error("Error parsing agent specification")
                    else:
                        st.error(f"Failed to load details for agent: {agent_name}")
            else:
                st.warning("Please enter an agent name")
    
    with tab3:
        st.header("➕ Create New Agent")
        st.info("Create a new agent in the target account")
        
        if not target_client:
            st.error("Target account not configured")
            st.stop()
        
        with st.form("create_agent_form"):
            st.subheader("Basic Information")
            new_agent_name = st.text_input("Agent Name", placeholder="MY_NEW_AGENT")
            new_agent_comment = st.text_area("Comment", placeholder="Description of the agent")
            
            st.subheader("Profile")
            display_name = st.text_input("Display Name", placeholder="My New Agent")
            
            st.subheader("Instructions")
            response_instructions = st.text_area("Response Instructions", placeholder="How should the agent respond?")
            orchestration_instructions = st.text_area("Orchestration Instructions", placeholder="How should the agent orchestrate?")
            system_instructions = st.text_area("System Instructions", placeholder="System-level instructions")
            
            st.subheader("Model Configuration")
            orchestration_model = st.selectbox(
                "Orchestration Model",
                ["claude-4-sonnet", "llama3.1-70B", "auto"],
                index=2
            )
            
            st.subheader("Budget Constraints")
            col1, col2 = st.columns(2)
            with col1:
                time_budget = st.number_input("Time Budget (seconds)", min_value=1, max_value=300, value=30)
            with col2:
                token_budget = st.number_input("Token Budget", min_value=1000, max_value=100000, value=16000)
            
            submitted = st.form_submit_button("🚀 Create Agent", type="primary")
            
            if submitted:
                if new_agent_name:
                    # Build agent configuration
                    agent_config = {
                        "name": new_agent_name,
                        "comment": new_agent_comment,
                        "profile": {
                            "display_name": display_name
                        },
                        "instructions": {
                            "response": response_instructions,
                            "orchestration": orchestration_instructions,
                            "system": system_instructions
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
                    
                    # Remove None values
                    agent_config = {k: v for k, v in agent_config.items() if v is not None}
                    if agent_config.get("models", {}).get("orchestration") is None:
                        agent_config["models"] = {}
                    
                    with st.spinner("Creating agent..."):
                        success = target_client.create_agent(
                            target_config['database'], 
                            target_config['schema'], 
                            agent_config
                        )
                        
                        if success:
                            st.success(f"Agent '{new_agent_name}' created successfully!")
                            st.balloons()
                        else:
                            st.error("Failed to create agent. Check the logs for details.")
                else:
                    st.warning("Please enter an agent name")
    
    with tab4:
        st.header("📊 Migration History")
        st.markdown("Track all cross-account migrations performed in this session")
        
        if st.session_state.migration_history:
            st.success(f"Found {len(st.session_state.migration_history)} migration(s) in this session")
            
            # Create DataFrame for better display
            migration_df = pd.DataFrame(st.session_state.migration_history)
            
            # Display the migration history
            st.dataframe(
                migration_df,
                use_container_width=True,
                column_config={
                    "timestamp": "Migration Time",
                    "source_account": "Source Account",
                    "source_agent": "Source Agent",
                    "source_db": "Source DB",
                    "source_schema": "Source Schema", 
                    "target_account": "Target Account",
                    "target_db": "Target DB",
                    "target_schema": "Target Schema",
                    "target_agent": "Target Agent",
                    "status": "Status"
                }
            )
            
            # Export functionality
            if st.button("📥 Export Migration History", type="secondary"):
                csv = migration_df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name=f"cross_account_migration_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            
            # Clear history option
            if st.button("🗑️ Clear Migration History", type="secondary"):
                st.session_state.migration_history = []
                st.rerun()
        else:
            st.info("No migrations have been performed yet. Use the 'Migration' tab to migrate agents between accounts.")
            
            # Show example of what migration history will look like
            with st.expander("📋 What will be tracked?"):
                st.markdown("""
                The migration history will track:
                - **Timestamp**: When the migration was performed
                - **Source Account**: Source Snowflake account URL
                - **Source Agent**: Original agent name
                - **Source Database/Schema**: Where the agent was migrated from
                - **Target Account**: Target Snowflake account URL
                - **Target Database/Schema**: Where the agent was migrated to
                - **Target Agent**: Final agent name in target environment
                - **Status**: Success or failure status
                """)

if __name__ == "__main__":
    main()