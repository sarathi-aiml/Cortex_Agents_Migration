# Snowflake Cortex Agent Cross-Account Migration Tool

A comprehensive Streamlit application for migrating Snowflake Cortex Agents between different Snowflake accounts and environments using the REST API.

## Features

- 🔄 **Cross-Account Migration**: Migrate agents between different Snowflake accounts
- 📋 **Agent Discovery**: List and explore agents in source accounts
- 🔍 **Detailed Agent View**: Comprehensive agent configuration display
- ➕ **Agent Creation**: Create new agents in target accounts
- 📊 **Migration Tracking**: Complete history of all migrations
- 🔗 **Connection Testing**: Test connectivity to both source and target accounts
- ⚙️ **Flexible Naming**: Multiple naming strategies for migrated agents

## Prerequisites

- Python 3.8 or higher
- Snowflake accounts with Cortex Agents enabled
- Personal Access Tokens (PAT) for both source and target accounts
 https://docs.snowflake.com/en/user-guide/programmatic-access-tokens
- `env.dev` file with your Snowflake configuration

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Configure your `env.dev` file with the following structure:
```
# SOURCE ACCOUNT CONFIGURATION (DEV Environment)
SOURCE_ACCOUNT_URL=https://dev-account.snowflakecomputing.com
SOURCE_PAT=your_source_pat_token
SOURCE_DATABASE=DEV_DATABASE
SOURCE_SCHEMA=DEV_SCHEMA
SOURCE_DEFAULT_AGENT=DEFAULT_AGENT_NAME

# TARGET ACCOUNT CONFIGURATION (PROD Environment)
TARGET_ACCOUNT_URL=https://prod-account.snowflakecomputing.com
TARGET_PAT=your_target_pat_token
TARGET_DATABASE=PROD_DATABASE
TARGET_SCHEMA=PROD_SCHEMA

# MIGRATION SETTINGS
MIGRATION_NAME_SUFFIX=_PROD
ADD_MIGRATION_METADATA=true
TEST_CONNECTIONS=true
```

## Usage

1. **Run the application:**
   ```bash
   streamlit run cortex_agent_migration.py
   ```

2. **Open your browser** and navigate to `http://localhost:8501`

3. **Configure your accounts** in the `env.dev` file:
   - **Source Account**: Where your original agents exist (DEV)
   - **Target Account**: Where you want to migrate agents (PROD)

4. **Test connections** using the sidebar buttons to verify connectivity

5. **Navigate through the tabs:**
   - **🚀 Migration**: Complete cross-account migration workflow
   - **📋 Agent Details**: View detailed agent information
   - **➕ Create Agent**: Create new agents in target account
   - **📊 Migration History**: Track all migrations

## Migration Workflow

### Step-by-Step Process:

1. **Load Source Agents**: Click "Refresh Agent List" to load agents from source account
2. **Select Agent**: Choose the agent you want to migrate from the dropdown
3. **Load Details**: Click "Load Agent Details" to fetch complete configuration
4. **Review Configuration**: Examine the raw JSON specification
5. **Configure Migration**: Choose naming strategy and review target settings
6. **Execute Migration**: Click "Execute Migration" to deploy to target account

### Migration Options:

- **Keep Original Name**: Use the same agent name in target environment
- **Add Suffix**: Append a suffix (e.g., `_PROD`) to distinguish environments
- **Custom Name**: Specify a completely new name for the target agent

## Configuration

### Environment Variables

#### Source Account (DEV Environment):
- `SOURCE_ACCOUNT_URL`: Your source Snowflake account URL
- `SOURCE_PAT`: Personal Access Token for source account
- `SOURCE_DATABASE`: Source database name
- `SOURCE_SCHEMA`: Source schema name
- `SOURCE_DEFAULT_AGENT`: Default agent name for quick access

#### Target Account (PROD Environment):
- `TARGET_ACCOUNT_URL`: Your target Snowflake account URL
- `TARGET_PAT`: Personal Access Token for target account
- `TARGET_DATABASE`: Target database name
- `TARGET_SCHEMA`: Target schema name

#### Migration Settings:
- `MIGRATION_NAME_SUFFIX`: Suffix to add to migrated agent names
- `ADD_MIGRATION_METADATA`: Add migration tracking to agent comments
- `TEST_CONNECTIONS`: Enable connection testing before migration

## API Endpoints Used

The application uses the following Snowflake Cortex Agents REST API endpoints:

- `GET /api/v2/databases` - Test connection and list databases
- `GET /api/v2/databases/{database}/schemas/{schema}/agents` - List agents
- `GET /api/v2/databases/{database}/schemas/{schema}/agents/{name}` - Get agent details
- `POST /api/v2/databases/{database}/schemas/{schema}/agents` - Create agent

## Cross-Account Migration Features

### 🔄 **Account Separation**
- Completely separate source and target account configurations
- Independent authentication for each account
- Connection testing for both accounts

### 📊 **Migration Tracking**
- Complete migration history with source and target account information
- Success/failure status tracking
- Exportable migration reports

### ⚙️ **Flexible Configuration**
- Multiple naming strategies
- Configurable migration metadata
- Environment-specific settings

### 🔗 **Connection Management**
- Real-time connection testing
- Detailed error reporting
- Account-specific error handling

## Error Handling

The application includes comprehensive error handling for:
- Network connectivity issues
- Authentication failures
- Invalid agent names
- Malformed JSON responses
- Missing environment variables
- Cross-account permission issues

## Security Notes

- Keep your Personal Access Tokens secure and never commit them to version control
- The `env.dev` file should be added to `.gitignore`
- Consider using environment variables instead of a file for production deployments
- Ensure PAT tokens have appropriate permissions for both accounts

## Troubleshooting

1. **"Source/Target account not configured"**: Update your `env.dev` file with correct account details
2. **Connection test failures**: Verify PAT tokens and account URLs
3. **"No agents found"**: Check database and schema names are correct
4. **Migration failures**: Ensure target account has proper permissions and resources

## Migration History

The application tracks:
- **Timestamp**: When the migration was performed
- **Source Account**: Source Snowflake account URL
- **Source Agent**: Original agent name and location
- **Target Account**: Target Snowflake account URL
- **Target Agent**: Final agent name and location
- **Status**: Success or failure with error details

## License

This project is provided as-is for educational and development purposes.
