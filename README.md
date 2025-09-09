# LG-RackandStack - Loan Data Processing Workflow

## Overview

**LG-RackandStack** is a comprehensive LangGraph workflow designed for automated loan data processing and document management. This workflow integrates with ESFuse APIs, Encompass loan management systems, and document repositories to create a complete loan processing pipeline.

## What's Included

### Complete Workflow Pipeline
The workflow includes six main processing nodes:
- **`extract_input`**: Parse and validate user input
- **`pull_data`**: Retrieve loan data from ESFuse API and auto-parse borrower information
- **`pull_doc`**: Download document data for all specified document IDs
- **`push_data`**: Update Encompass loan fields with parsed borrower data
- **`push_doc`**: Create loan submissions and associate documents
- **`summary`**: Generate comprehensive workflow reporting

### Advanced State Management
- **`State`** class with comprehensive fields:
  - `user_input`: JSON input with loan/document data
  - `loan_id`, `task_id`, `client_id`: Core identifiers
  - `document_ids`: JSON array of document IDs to process
  - `field_updates`: Auto-generated Encompass field mappings
  - Workflow tracking: `pull_data_result`, `push_data_result`, etc.

### API Integrations
- **ESFuse APIs**: Loan and document data retrieval
- **Encompass Integration**: Automatic field updates with parsed borrower data
- **TaskDoc/DocRepo**: Document submission and task management
- **Async Processing**: Non-blocking API calls for performance

## Getting Started

### Prerequisites
- Python 3.9+
- LangGraph
- cuteagent (Document and loan processing library)
- aiohttp (for async API calls)

### Required Environment Variables
Create a `.env` file with the following variables:
```bash
# ESFuse API Configuration
ESFUSE_TOKEN=your_esfuse_token
LOAN_API_BASE_URL=https://your-loan-api.com/prod
DOC_API_BASE_URL=https://your-doc-api.com/prod

# Encompass API Configuration  
ENCOMPASS_BASE_URL=https://your-encompass-api.com
ENCOMPASS_ACCESS_TOKEN=your_encompass_token

# TaskDoc API Configuration
TASKDOC_API_TOKEN=your_taskdoc_api_token
TASKDOC_AUTH_TOKEN=your_taskdoc_auth_token

# Submission Configuration (optional)
SUBMISSION_TYPE=Initial Submission
AUTO_LOCK=false
```

### Installation
```bash
# Navigate to project directory
cd LG-RackandStack-main

# Install dependencies
pip install -e .

# Run the workflow
langgraph dev
```

## Workflow Process

### Input Format
The workflow accepts JSON input with the following structure:
```json
{
  "status": "completed",
  "loan_id": "25",
  "task_id": "347360", 
  "client_id": "loan_25",
  "document_ids": "[\"953\", \"954\", \"955\", \"956\", \"957\", \"958\", \"959\", \"960\", \"962\", \"963\", \"964\", \"965\", \"966\", \"967\", \"968\", \"969\"]",
  "documents_stored": "16",
  "documents_processed": "17"
}
```

### Processing Flow
```
START → extract_input → pull_data → pull_doc → push_data → push_doc → summary → END
```

#### 1. **extract_input**
- Validates environment variables
- Parses input JSON and extracts all required fields
- Sets up state for subsequent nodes

#### 2. **pull_data** 
- Calls ESFuse loan API: `GET /loan?clientId={client_id}&loanId={loan_id}`
- **Automatically parses borrower data** and creates Encompass field mappings:
  - `4000`: first_name
  - `4001`: middle_name  
  - `4002`: last_name
  - `1204`: email
  - `65`: SSN
  - `1402`: date_of_birth
  - `FR0106`: city
  - `FR0126`: address1
- Stores parsed field updates in state

#### 3. **pull_doc**
- Processes all document IDs from the input array
- Calls ESFuse doc API: `GET /doc?clientId={client_id}&docId={doc_id}` for each document
- Handles both JSON and PDF responses
- Creates summary with success/failure counts

#### 4. **push_data**
- Uses the auto-generated field updates from pull_data
- Retrieves Encompass loan GUID from the loan API
- Updates Encompass: `POST /api/v1/write_loan_data`
- Pushes all parsed borrower data to corresponding Encompass fields

#### 5. **push_doc**
- Creates loan submission using the CuteAgent library
- Library internally handles task processing using the `task_id`
- Associates all documents with the submission
- Supports submission types and auto-lock functionality

#### 6. **summary**
- Generates comprehensive workflow report
- Shows success/failure status for each node
- Provides document processing statistics
- Creates final workflow summary

## Key Features

### Automatic Field Mapping
The workflow automatically extracts borrower information from loan data and maps it to Encompass field IDs:

| **Data Field** | **Encompass Field ID** | **Source** |
|----------------|------------------------|------------|
| First Name | 4000 | `loaninfo.borrowers_attributes[0].first_name` |
| Middle Name | 4001 | `loaninfo.borrowers_attributes[0].middle_name` |
| Last Name | 4002 | `loaninfo.borrowers_attributes[0].last_name` |
| Email | 1204 | `loaninfo.borrowers_attributes[0].email` |
| SSN | 65 | `loaninfo.borrowers_attributes[0].ssn` |
| Date of Birth | 1402 | `loaninfo.borrowers_attributes[0].date_of_birth` |
| City | FR0106 | `loaninfo.city` |
| Address 1 | FR0126 | `loaninfo.address1` |

### Error Handling & Logging
- Comprehensive error handling at each node
- Detailed logging for debugging and monitoring
- Graceful failure handling with error reporting
- State tracking throughout the workflow

### Performance Optimizations
- Async API calls using `aiohttp` for non-blocking operations
- Efficient JSON parsing and data extraction
- Minimal memory footprint (no file downloads)
- Parallel document processing capabilities

## Development

### File Structure
```
LG-RackandStack-main/
├── src/agent/
│   ├── __init__.py
│   └── graph.py          # Main workflow definition
├── lgBlank.egg-info/     # Package metadata
├── pyproject.toml        # Project dependencies and configuration
├── langgraph.json        # LangGraph configuration
├── workflow_config.json  # Workflow configuration template
└── README.md            # This file
```

### Testing & Development
Use LangGraph Studio to test and develop:
1. **Start the development server:**
   ```bash
   langgraph dev
   ```

2. **Access the interfaces:**
   - 🚀 **API:** http://127.0.0.1:2024
   - 🎨 **Studio UI:** https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
   - 📚 **API Docs:** http://127.0.0.1:2024/docs

3. **Test with sample input:**
   ```json
   {
     "loan_id": "25",
     "task_id": "347360",
     "client_id": "loan_25", 
     "document_ids": "[\"953\", \"954\"]"
   }
   ```

### Workflow Configuration
The `workflow_config.json` file can be used to customize:
- API endpoints and tokens
- Field mapping configurations
- Submission settings
- Error handling preferences

## API Reference

### Input Parameters
- **`loan_id`** (required): Unique loan identifier
- **`task_id`** (required): TaskDoc task identifier for document processing
- **`client_id`** (required): ESFuse client identifier
- **`document_ids`** (required): JSON array of document IDs to process
- **`documents_stored`** (optional): Count of stored documents
- **`documents_processed`** (optional): Count of processed documents

### Output Structure
```json
{
  "workflow_status": "Success",
  "total_nodes_completed": 6,
  "pull_data_success": true,
  "pull_doc_success": true, 
  "push_data_success": true,
  "push_doc_success": true,
  "documents_processed": 16,
  "successful_documents": 15,
  "failed_documents": 1,
  "timestamp": "2025-01-04 23:45:30"
}
```

## License

This template follows the same license as the parent project.
