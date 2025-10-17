"""LangGraph workflow based on JSON instructions.

Creates a blank template for Windows automation workflows.
"""

from __future__ import annotations

import json
import os
from typing import Union, Dict, Any, Optional, Tuple, List
from pydantic import BaseModel
import asyncio
import logging
import datetime
import aiohttp

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph
from cuteagent import DocumentAgent  # type: ignore
from dotenv import load_dotenv

# Set environment variable to handle blocking operations properly
os.environ["BG_JOB_ISOLATED_LOOPS"] = "true"

doc_agent = DocumentAgent()

load_dotenv()

# =============================================================================
# ENVIRONMENT VARIABLES
# =============================================================================

# Load environment variables for configuration
# ESFuse API Configuration
ESFUSE_TOKEN = os.getenv("ESFUSE_TOKEN")
LOAN_API_BASE_URL = os.getenv("LOAN_API_BASE_URL")
DOC_API_BASE_URL = os.getenv("DOC_API_BASE_URL")

# Encompass API Configuration
ENCOMPASS_BASE_URL = os.getenv("ENCOMPASS_BASE_URL")
ENCOMPASS_ACCESS_TOKEN = os.getenv("ENCOMPASS_ACCESS_TOKEN")

# TaskDoc API Configuration
TASKDOC_API_TOKEN = os.getenv("TASKDOC_API_TOKEN")
TASKDOC_AUTH_TOKEN = os.getenv("TASKDOC_AUTH_TOKEN")

# Submission Configuration
SUBMISSION_TYPE = os.getenv("SUBMISSION_TYPE", "Initial Submission")
AUTO_LOCK = os.getenv("AUTO_LOCK", "false").lower() == "true"

# Validate required environment variables
def validate_environment():
    """Validate that all required environment variables are set."""
    required_vars = [
        "ESFUSE_TOKEN",
        "LOAN_API_BASE_URL", 
        "DOC_API_BASE_URL",
        "ENCOMPASS_BASE_URL",
        "ENCOMPASS_ACCESS_TOKEN",
        "TASKDOC_API_TOKEN",
        "TASKDOC_AUTH_TOKEN"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    logging.info("✅ All required environment variables are set")

# Note: Environment validation will be done at runtime in the first node

# =============================================================================
# ASYNC API HELPERS
# =============================================================================

async def async_pull_loan_data(client_id: str, loan_id: str, esfuse_token: str, get_api_base: str) -> Dict[str, Any]:
    """Async version of DocumentAgent pull_data for loan data."""
    try:
        api_url = f"{get_api_base}/loan?clientId={client_id}&loanId={loan_id}"
        headers = {"Authorization": f"Bearer {esfuse_token}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    raw_data = await response.json()
                    
                    # Parse the data (simplified version of the original parsing)
                    parsed_data = {
                        "client_id": client_id,
                        "loan_id": loan_id,
                        "api_url": api_url,
                        "status": "success"
                    }
                    
                    # Extract some basic loan info if available
                    if isinstance(raw_data, dict):
                        parsed_data["raw_keys"] = list(raw_data.keys())
                        if "clientId" in raw_data:
                            parsed_data["response_client_id"] = raw_data["clientId"]
                        if "loanId" in raw_data:
                            parsed_data["response_loan_id"] = raw_data["loanId"]
                    
                    return {
                        "success": True,
                        "raw": raw_data,
                        "parsed": parsed_data,
                        "api_url": api_url,
                        "client_id": client_id,
                        "loan_id": loan_id
                    }
                else:
                    return {
                        "success": False,
                        "error": f"API call failed with status {response.status}: {await response.text()}",
                        "api_url": api_url
                    }
    except Exception as e:
        return {
            "success": False,
            "error": f"API request failed: {str(e)}"
        }

async def async_pull_doc_data(api_base: str, token: str, client_id: str, doc_id: str) -> Dict[str, Any]:
    """Async version of DocumentAgent pull_doc for document data."""
    try:
        api_url = f"{api_base}/doc?clientId={client_id}&docId={doc_id}"
        headers = {"Authorization": f"Bearer {token}"}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    # Try to parse as JSON first
                    try:
                        response_data = await response.json()
                        return {
                            "success": True,
                            "response_type": "json",
                            "response_data": response_data,
                            "api_url": api_url,
                            "client_id": client_id,
                            "doc_id": doc_id
                        }
                    except:
                        # If not JSON, treat as binary (PDF) but don't save
                        content = await response.read()
                        
                        return {
                            "success": True,
                            "response_type": "pdf",
                            "file_size": len(content),
                            "api_url": api_url,
                            "client_id": client_id,
                            "doc_id": doc_id
                        }
                else:
                    return {
                        "success": False,
                        "error": f"API request failed with status {response.status}",
                        "response_text": await response.text(),
                        "status_code": response.status
                    }
    except Exception as e:
        return {
            "success": False,
            "error": f"Request failed: {str(e)}"
        }

async def async_push_data(field_updates: Dict, client_id: str, loan_id: str, 
                         get_api_base: str, esfuse_token: str, base_url: str, access_token: str) -> Dict[str, Any]:
    """Async version of DocumentAgent push_data for Encompass updates."""
    try:
        # Use loan_id directly as the encompass_loan_guid
        encompass_loan_guid = loan_id
        
        logging.info(f"Using loan_id as encompass_loan_guid: {encompass_loan_guid}")
        
        # Push updates to Encompass
        write_loan_url = f"{base_url}/api/v1/write_loan_data?token={access_token}"
        request_body = {
            "encompass_loan_guid": encompass_loan_guid,
            "json_data": json.dumps(field_updates)
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(write_loan_url, json=request_body, timeout=30) as response:
                if response.status == 200:
                    response_data = await response.json() if response.content_length else None
                    return {
                        "success": True,
                        "encompass_loan_guid": encompass_loan_guid,
                        "fields_updated": list(field_updates.keys()),
                        "response": response_data,
                        "status_code": response.status
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Encompass API request failed with status {response.status}",
                        "response_text": await response.text(),
                        "status_code": response.status
                    }
    except Exception as e:
        return {
            "success": False,
            "error": f"Push data error: {str(e)}"
        }

# =============================================================================
# STATE DEFINITION
# =============================================================================

class State(BaseModel):
    """State for the LangGraph workflow - only accepts specific input types."""
    # User input fields (only these are accepted from user input)
    user_input: str = ""
    current_node: int = 0
    status: str = ""
    
    # Allowed input fields from user (matching your specification)
    loan_id: str = ""
    task_id: str = ""
    client_id: str = ""
    document_ids: str = ""
    documents_stored: str = ""
    documents_processed: str = ""
    
    # Internal state fields (not from user input)
    loan_data: Dict[str, Any] = {}
    documents_stored_list: List[Dict[str, Any]] = []
    
    # Field updates for Encompass (user can provide field_id: value mappings)
    # Common field IDs:
    # 4000: first_name, 4001: middle_name, 4002: last_name
    # 1204: email, 65: SSN, 1402: date_of_birth
    # FR0106: city, FR0126: address_1
    field_updates: Dict[str, str] = {}
    
    # Workflow state fields
    pull_data_result: Dict[str, Any] = {}
    pull_doc_results: List[Dict[str, Any]] = []
    push_data_result: Dict[str, Any] = {}
    push_doc_result: Dict[str, Any] = {}
    workflow_summary: Dict[str, Any] = {}

# =============================================================================
# CONFIGURATION
# =============================================================================

# OS URL - update this to point to your Windows server
# OS_URL = "https://fintor-ec2-dev.ngrok.app"

# =============================================================================
# ACTION FUNCTIONS
# These are reusable building blocks for creating your workflow nodes
# =============================================================================


async def extract_input_fields(state: State, config: RunnableConfig) -> State:
    """Extract only allowed fields from user_input (string JSON or dict format)."""
    try:
        # Validate environment variables at runtime
        await asyncio.to_thread(validate_environment)
        if state.user_input:
            if isinstance(state.user_input, str):
                # Try to parse as JSON
                try:
                    input_data = json.loads(state.user_input)
                except json.JSONDecodeError:
                    # If not JSON, treat as plain text
                    input_data = {}
            elif isinstance(state.user_input, dict):
                input_data = state.user_input
            else:
                input_data = {}
            
            # Extract only the allowed fields from user input
            if "loan_id" in input_data:
                state.loan_id = str(input_data["loan_id"])
                logging.info(f"Extracted loan_id: {state.loan_id}")
            
            if "task_id" in input_data:
                state.task_id = str(input_data["task_id"])
                logging.info(f"Extracted task_id: {state.task_id}")
            
            if "client_id" in input_data:
                state.client_id = str(input_data["client_id"])
                logging.info(f"Extracted client_id: {state.client_id}")
            
            if "document_ids" in input_data:
                state.document_ids = str(input_data["document_ids"])
                logging.info(f"Extracted document_ids: {state.document_ids}")
            
            if "documents_stored" in input_data:
                state.documents_stored = str(input_data["documents_stored"])
                logging.info(f"Extracted documents_stored: {state.documents_stored}")
            
            if "documents_processed" in input_data:
                state.documents_processed = str(input_data["documents_processed"])
                logging.info(f"Extracted documents_processed: {state.documents_processed}")
            
            if "field_updates" in input_data and isinstance(input_data["field_updates"], dict):
                state.field_updates = {str(k): str(v) for k, v in input_data["field_updates"].items()}
                logging.info(f"Extracted field_updates: {state.field_updates}")
            
            # All fields now have defaults, so no validation needed
            state.status = "Success"
            
            state.current_node = 1
        else:
            logging.warning("No user_input provided")
            state.status = "Error"
            state.loan_data = {"error": "No user_input provided"}
            state.current_node = 1
            
    except Exception as e:
        logging.error(f"Error extracting input fields: {e}")
        state.current_node = 1
        state.status = "Error"
    
    return state

async def pull_data_node(state: State, config: RunnableConfig) -> State:
    """Pull loan data using DocumentAgent ESFuse functionality."""
    try:
        loan_id = state.loan_id
        client_id = state.client_id
        
        logging.info(f"Pulling data for loan_id: {loan_id}")
        logging.info(f"API URL: {LOAN_API_BASE_URL}")
        logging.info(f"Client ID: {client_id}")
        logging.info(f"ESFuse Token: {ESFUSE_TOKEN[:10]}..." if ESFUSE_TOKEN and len(ESFUSE_TOKEN) > 10 else f"ESFuse Token: {ESFUSE_TOKEN}")
        
        # Pull loan data using async API
        result = await async_pull_loan_data(
            client_id=client_id,
            loan_id=loan_id,
            esfuse_token=ESFUSE_TOKEN,
            get_api_base=LOAN_API_BASE_URL
        )
        
        # Check if the result contains an error
        if result.get("success", False):
            state.pull_data_result = result
            state.loan_data = result
            logging.info(f"Successfully pulled loan data!")
            logging.info(f"Client ID: {result.get('client_id')}")
            logging.info(f"Loan ID: {result.get('loan_id')}")
            logging.info(f"API URL: {result.get('api_url')}")
            
            # Parse loan data from raw response and create field updates
            raw_data = result.get("raw", {})
            if raw_data and "loaninfo" in raw_data:
                loaninfo = raw_data["loaninfo"]
                field_updates = {}
                
                # Parse borrower information from borrowers_attributes array
                borrowers = loaninfo.get("borrowers_attributes", [])
                if borrowers:
                    # Find main borrower or use first borrower
                    main_borrower = None
                    for borrower in borrowers:
                        if borrower.get("main_borrower", False):
                            main_borrower = borrower
                            break
                    if not main_borrower:
                        main_borrower = borrowers[0]
                    
                    logging.info(f"Processing borrower: {main_borrower.get('first_name')} {main_borrower.get('last_name')}")
                    
                    # Map borrower fields to Encompass field IDs
                    if main_borrower.get("first_name"):
                        field_updates["4000"] = main_borrower["first_name"]
                        logging.info(f"  ✓ first_name: {main_borrower['first_name']}")
                    
                    if main_borrower.get("middle_name"):
                        field_updates["4001"] = main_borrower["middle_name"]
                        logging.info(f"  ✓ middle_name: {main_borrower['middle_name']}")
                    
                    if main_borrower.get("last_name"):
                        field_updates["4002"] = main_borrower["last_name"]
                        logging.info(f"  ✓ last_name: {main_borrower['last_name']}")
                    
                    if main_borrower.get("email"):
                        field_updates["1204"] = main_borrower["email"]
                        logging.info(f"  ✓ email: {main_borrower['email']}")
                    
                    if main_borrower.get("ssn"):
                        field_updates["65"] = main_borrower["ssn"]
                        logging.info(f"  ✓ ssn: {main_borrower['ssn']}")
                    
                    if main_borrower.get("date_of_birth"):
                        field_updates["1402"] = main_borrower["date_of_birth"]
                        logging.info(f"  ✓ date_of_birth: {main_borrower['date_of_birth']}")
                
                # Parse property/address information
                logging.info(f"Processing property information:")
                
                if loaninfo.get("address1"):
                    field_updates["FR0126"] = loaninfo["address1"]
                    logging.info(f"  ✓ address1: {loaninfo['address1']}")
                
                if loaninfo.get("city"):
                    field_updates["FR0106"] = loaninfo["city"]
                    logging.info(f"  ✓ city: {loaninfo['city']}")
                
                if loaninfo.get("state"):
                    field_updates["FR0107"] = loaninfo["state"]
                    logging.info(f"  ✓ state: {loaninfo['state']}")
                
                if loaninfo.get("zip_code"):
                    field_updates["FR0108"] = loaninfo["zip_code"]
                    logging.info(f"  ✓ zip_code: {loaninfo['zip_code']}")
                
                # Store parsed field updates in state for push_data_node
                state.field_updates = field_updates
                logging.info(f"✅ Created {len(field_updates)} field updates from loan data")
                logging.info(f"Field IDs: {list(field_updates.keys())}")
            
            state.status = "Success"
        else:
            error_msg = result.get('error', 'Unknown error')
            logging.error(f"Failed to pull loan data: {error_msg}")
            state.status = "Error"
            state.pull_data_result = {"error": error_msg}
            state.loan_data = {"error": error_msg}
        
        state.current_node = 2
        return state
        
    except Exception as e:
        logging.error(f"Error in pull_data_node: {e}")
        state.current_node = 2
        state.status = "Error"
        state.loan_data = {"error": str(e)}
        return state

async def pull_doc_node(state: State, config: RunnableConfig) -> State:
    """Pull data for all documents in the document_ids list and save to JSON file."""
    try:
        # Parse the document_ids JSON string
        if state.document_ids:
            import json
            doc_ids = json.loads(state.document_ids)
            logging.info(f"Processing {len(doc_ids)} documents: {doc_ids}")
            
            all_documents_data = []
            for doc_id in doc_ids:
                # Pull document data using async API
                result = await async_pull_doc_data(
                    api_base=DOC_API_BASE_URL,
                    token=ESFUSE_TOKEN,
                    client_id=state.client_id,
                    doc_id=str(doc_id)
                )
                
                # Handle the result from pull_doc
                if result.get("success", False):
                    clean_result = {
                        "doc_id": doc_id,
                        "response_type": result.get("response_type"),
                        "api_url": result.get("api_url"),
                        "client_id": result.get("client_id"),
                        "success": True
                    }
                    
                    # Add response data based on type
                    if result.get("response_type") == "json":
                        clean_result["response_data"] = result.get("response_data", {})
                        logging.info(f"Successfully pulled JSON data for document {doc_id}")
                    elif result.get("response_type") == "pdf":
                        clean_result["file_size"] = result.get("file_size")
                        logging.info(f"Successfully retrieved PDF data for document {doc_id} (size: {result.get('file_size', 0)} bytes)")
                    
                    all_documents_data.append(clean_result)
                    logging.info(f"Successfully processed document {doc_id}")
                    
                else:
                    logging.error(f"Failed to pull data for document {doc_id}: {result.get('error')}")
                    all_documents_data.append({
                        "doc_id": doc_id,
                        "error": result.get("error", "Unknown error"),
                        "success": False
                    })
            
            # Create the final output structure
            output_data = {
                "loan_id": state.loan_id,
                "client_id": state.client_id,
                "task_id": state.task_id,
                "status": state.status,
                "total_documents": len(doc_ids),
                "successful_pulls": len([doc for doc in all_documents_data if doc.get("success", False)]),
                "failed_pulls": len([doc for doc in all_documents_data if not doc.get("success", False)]),
                "documents": all_documents_data,
                "timestamp": await asyncio.to_thread(lambda: str(datetime.datetime.now()))
            }
            
            # Store the documents data in state for use by push_data_node
            state.pull_doc_results = all_documents_data
            state.documents_stored_list = all_documents_data
            state.loan_data = output_data
            state.status = "Success"
        else:
            state.status = "Error"
            state.loan_data = {"error": "No document_ids provided"}
        
        state.current_node = 3
        return state
        
    except Exception as e:
        logging.error(f"Error in pull_all_documents_node: {e}")
        state.current_node = 2
        state.status = "Error"
        state.loan_data = {"error": str(e)}
        return state

async def push_data_node(state: State, config: RunnableConfig) -> State:
    """Push field updates to Encompass using DocumentAgent ESFuse functionality."""
    try:
        # Use hardcoded field updates for testing
        field_updates = state.field_updates if state.field_updates else {"4000": "DefaultTestValue"}
        # field_updates = {"4000": "Nick"}
        client_id = state.client_id
        loan_id = state.loan_id
        get_api_base = LOAN_API_BASE_URL
        esfuse_token = ESFUSE_TOKEN
        base_url = ENCOMPASS_BASE_URL
        access_token = ENCOMPASS_ACCESS_TOKEN
        
        logging.info(f"Pushing field updates for loan: {loan_id}")
        logging.info(f"Client ID: {client_id}")
        logging.info(f"Fields to update: {list(field_updates.keys())}")
        logging.info(f"Field values: {field_updates}")
        logging.info(f"Encompass URL: {base_url}")
        
        # Push data using async API
        result = await async_push_data(
            field_updates=field_updates,
            client_id=client_id,
            loan_id=loan_id,
            get_api_base=get_api_base,
            esfuse_token=esfuse_token,
            base_url=base_url,
            access_token=access_token
        )
        
        # Check if the result contains an error
        if result.get("success", False):
            state.push_data_result = result
            state.loan_data = result
            logging.info(f"Successfully pushed field updates to Encompass")
            logging.info(f"Encompass GUID: {result.get('encompass_loan_guid')}")
            logging.info(f"Fields updated: {result.get('fields_updated', [])}")
            logging.info(f"Status code: {result.get('status_code', 'N/A')}")
            state.status = "Success"
        else:
            error_msg = result.get('error', 'Unknown error')
            logging.error(f"Failed to push field updates: {error_msg}")
            state.status = "Error"
            state.push_data_result = {"error": error_msg}
            state.loan_data = {"error": error_msg}
        
        state.current_node = 4
        return state
        
    except Exception as e:
        logging.error(f"Error in push_data_node: {e}")
        state.current_node = 3
        state.status = "Error"
        state.loan_data = {"error": str(e)}
        return state

async def push_doc_node(state: State, config: RunnableConfig) -> State:
    """Create loan submission and associate documents using DocumentAgent ESFuse functionality."""
    try:
        # Use values from state
        submission_type = SUBMISSION_TYPE
        auto_lock = AUTO_LOCK
        client_id = state.client_id
        loan_id = state.loan_id
        
        # Parse document_ids from state - keep as array
        import json
        if state.document_ids:
            try:
                doc_ids = json.loads(state.document_ids)
                # Convert to integers if they're numeric strings
                doc_ids = [int(doc_id) if str(doc_id).isdigit() else doc_id for doc_id in doc_ids]
            except json.JSONDecodeError:
                # If it's not valid JSON, treat as single document ID
                doc_ids = [state.document_ids]
        else:
            doc_ids = [953]  # Fallback document ID
        
        token = ESFUSE_TOKEN
        api_base = DOC_API_BASE_URL
        taskdoc_api_token = TASKDOC_API_TOKEN
        taskdoc_auth_token = TASKDOC_AUTH_TOKEN
        
        logging.info(f"Creating submission using push_doc method")
        logging.info(f"Client ID: {client_id}")
        logging.info(f"Loan ID: {loan_id}")
        logging.info(f"Document IDs: {doc_ids}")
        logging.info(f"API Base: {api_base}")
        logging.info(f"Submission type: {submission_type}")
        logging.info(f"Auto lock: {auto_lock}")
        
        # Push document using DocumentAgent with array of document IDs
        # API Endpoint: POST /api/v5/loans/:loan_id/submissions?token={{API_TOKEN}}
        # The library internally uses task_id to extract TaskDoc data before submission
        logging.info(f"📤 Calling doc_agent.ESFuse.push_doc...")
        
        result = await asyncio.to_thread(
            doc_agent.ESFuse.push_doc,
            client_id=client_id,
            direct_loan_id=loan_id,  # Required for API path: /loans/{loan_id}/submissions
            # direct_document_ids=doc_ids,  # Maps to body: document_ids
            # direct_api_token=token,  # Maps to query param: ?token=
            # direct_base_url=api_base,
            submission_type=submission_type,  # Maps to body: submission_type
            auto_lock=auto_lock,  # Maps to body: auto_lock
            taskdoc_api_token=taskdoc_api_token,
            taskdoc_auth_token=taskdoc_auth_token,

            doc_id = doc_ids,
            token = token,
            api_base = api_base
        )
        
        logging.info(f"📦 push_doc returned: {result}")
        # Check if the result contains an error
        if result.get("success", False):
            state.push_doc_result = result
            state.loan_data = result
            logging.info(f"Successfully created loan submission")
            logging.info(f"Message: {result.get('message', 'N/A')}")
            
            # Log DocRepo fields if available
            docrepo_fields = result.get("docrepo_fields", {})
            if docrepo_fields:
                logging.info(f"Task ID: {docrepo_fields.get('taskId', 'N/A')}")
                logging.info(f"Loan ID: {docrepo_fields.get('loanId', 'N/A')}")
                
                # Log submission results if available
                submission_result = docrepo_fields.get('submission_result', {})
                if submission_result:
                    logging.info(f"Submission Success: {submission_result.get('success', False)}")
                    logging.info(f"Submission Status Code: {submission_result.get('status_code', 'N/A')}")
            
            state.status = "Success"
        else:
            error_msg = result.get('error', 'Unknown error')
            logging.error(f"Failed to create submission: {error_msg}")
            state.status = "Error"
            state.push_doc_result = {"error": error_msg}
            state.loan_data = {"error": error_msg}
        
        state.current_node = 5
        return state
        
    except Exception as e:
        logging.error(f"Error in push_doc_node: {e}")
        state.current_node = 4
        state.status = "Error"
        state.loan_data = {"error": str(e)}
        return state

async def workflow_summary_node(state: State, config: RunnableConfig) -> State:
    """Create a comprehensive workflow summary."""
    try:
        summary = {
            "workflow_status": state.status,
            "total_nodes_completed": state.current_node,
            "pull_data_success": state.pull_data_result.get("success", False) if state.pull_data_result else False,
            "pull_doc_success": len([doc for doc in state.pull_doc_results if doc.get("success", False)]) > 0 if state.pull_doc_results else False,
            "push_data_success": state.push_data_result.get("success", False) if state.push_data_result else False,
            "push_doc_success": state.push_doc_result.get("success", False) if state.push_doc_result else False,
            "documents_processed": len(state.pull_doc_results) if state.pull_doc_results else 0,
            "successful_documents": len([doc for doc in state.pull_doc_results if doc.get("success", False)]) if state.pull_doc_results else 0,
            "failed_documents": len([doc for doc in state.pull_doc_results if not doc.get("success", False)]) if state.pull_doc_results else 0,
            "timestamp": str(datetime.datetime.now())
        }
        
        state.workflow_summary = summary
        state.loan_data = summary
        
        logging.info("=" * 60)
        logging.info("WORKFLOW SUMMARY")
        logging.info("=" * 60)
        logging.info(f"Overall Status: {summary['workflow_status']}")
        logging.info(f"Nodes Completed: {summary['total_nodes_completed']}")
        logging.info(f"Pull Data: {'✅' if summary['pull_data_success'] else '❌'}")
        logging.info(f"Pull Docs: {'✅' if summary['pull_doc_success'] else '❌'}")
        logging.info(f"Push Data: {'✅' if summary['push_data_success'] else '❌'}")
        logging.info(f"Push Docs: {'✅' if summary['push_doc_success'] else '❌'}")
        logging.info(f"Documents Processed: {summary['documents_processed']}")
        logging.info(f"Successful Documents: {summary['successful_documents']}")
        logging.info(f"Failed Documents: {summary['failed_documents']}")
        logging.info("=" * 60)
        
        return state
        
    except Exception as e:
        logging.error(f"Error in workflow_summary_node: {e}")
        state.workflow_summary = {"error": str(e)}
        return state


# =============================================================================
# GRAPH COMPILATION
# Define and compile your workflow graph here
# =============================================================================

# Define your graph here - comprehensive workflow
graph = (
    StateGraph(State)
    .add_node("extract_input", extract_input_fields)
    .add_node("pull_data", pull_data_node)
    # .add_node("pull_doc", pull_doc_node)
    .add_node("push_data", push_data_node)
    .add_node("push_doc", push_doc_node)
    .add_node("summary", workflow_summary_node)
    
    .add_edge("__start__", "extract_input")
    .add_edge("extract_input", "pull_data")
    .add_edge("pull_data", "push_data")
    # .add_edge("pull_doc", "push_data")
    .add_edge("push_data", "push_doc")
    .add_edge("push_doc", "summary")
    .add_edge("summary", "__end__")
    .compile(
        name="lgRackandStack",
        checkpointer=None,  # Disable checkpointing to avoid blocking calls
    )
)

