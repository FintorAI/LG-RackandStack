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

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph
from cuteagent import WindowsAgent, DocumentAgent  # type: ignore
from dotenv import load_dotenv

doc_agent = DocumentAgent()

load_dotenv()

# =============================================================================
# ENVIRONMENT VARIABLES
# =============================================================================

# Load environment variables for configuration
ESFUSE_TOKEN = os.getenv("ESFUSE_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL")
ENCOMPASS_LOAN_GUID = os.getenv("ENCOMPASS_LOAN_GUID", "default_loan_guid")
SUBMISSION_TYPE = os.getenv("SUBMISSION_TYPE", "Initial Submission")
AUTO_LOCK = os.getenv("AUTO_LOCK", "true").lower() == "true"


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
            
            # Validate required fields
            missing_fields = []
            if not state.loan_id:
                missing_fields.append("loan_id")
            if not state.client_id:
                missing_fields.append("client_id")
            if not state.document_ids:
                missing_fields.append("document_ids")
            
            if missing_fields:
                error_msg = f"Missing required fields: {', '.join(missing_fields)}"
                logging.error(error_msg)
                state.status = "Error"
                state.loan_data = {"error": error_msg}
            else:
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
        # Require these values from user input
        if not state.loan_id:
            logging.error("loan_id is required from user input")
            state.status = "Error"
            state.loan_data = {"error": "loan_id is required from user input"}
            state.current_node = 2
            return state
            
        if not state.client_id:
            logging.error("client_id is required from user input")
            state.status = "Error"
            state.loan_data = {"error": "client_id is required from user input"}
            state.current_node = 2
            return state
        
        loan_id = state.loan_id
        client_id = state.client_id
        
        logging.info(f"Pulling data for loan_id: {loan_id}")
        logging.info(f"API URL: {API_BASE_URL}")
        logging.info(f"Client ID: {client_id}")
        logging.info(f"ESFuse Token: {ESFUSE_TOKEN[:10]}..." if ESFUSE_TOKEN and len(ESFUSE_TOKEN) > 10 else f"ESFuse Token: {ESFUSE_TOKEN}")
        
        # Pull data for ALL documents in document_ids
        all_documents_data = []
        
        if state.document_ids:
            try:
                doc_ids = json.loads(state.document_ids)
                logging.info(f"Processing {len(doc_ids)} documents: {doc_ids}")
                
                for doc_id in doc_ids:
                    logging.info(f"Pulling data for document {doc_id}")
                    
                    result = await asyncio.to_thread(
                        doc_agent.ESFuse.pull_data,
                        client_id=client_id,
                        loan_id=loan_id,
                        doc_id=str(doc_id),
                        esfuse_token=ESFUSE_TOKEN,
                        get_api_url=API_BASE_URL
                    )
                    
                    # Check if the result contains an error
                    if "error" not in result:
                        # Remove raw data from the result
                        clean_result = {k: v for k, v in result.items() if k != '_raw_response'}
                        document_data = {
                            "doc_id": doc_id,
                            "data": clean_result,
                            "status": "success"
                        }
                        all_documents_data.append(document_data)
                        logging.info(f"Successfully pulled data for document {doc_id}")
                    else:
                        document_data = {
                            "doc_id": doc_id,
                            "error": result.get("error", "Unknown error"),
                            "status": "error"
                        }
                        all_documents_data.append(document_data)
                        logging.error(f"Failed to pull data for document {doc_id}: {result.get('error', 'Unknown error')}")
                
                # Save all documents data to local JSON file
                all_docs_filename = f"loan_{loan_id}_all_documents_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                
                def write_all_docs_json_file(filename, data):
                    with open(filename, 'w') as f:
                        json.dump(data, f, indent=2)
                
                await asyncio.to_thread(write_all_docs_json_file, all_docs_filename, all_documents_data)
                logging.info(f"Saved all documents data to {all_docs_filename}")
                
                # Store the combined data in state
                state.loan_data = {
                    "total_documents": len(doc_ids),
                    "successful_documents": len([d for d in all_documents_data if d["status"] == "success"]),
                    "failed_documents": len([d for d in all_documents_data if d["status"] == "error"]),
                    "documents": all_documents_data
                }
                
                state.status = "Success"
                
            except (json.JSONDecodeError, IndexError) as e:
                logging.error(f"Could not parse document_ids: {e}")
                state.status = "Error"
                state.loan_data = {"error": f"Could not parse document_ids: {e}"}
        else:
            logging.error("No document_ids provided")
            state.status = "Error"
            state.loan_data = {"error": "No document_ids provided"}
        
        state.current_node = 2
        return state
        
        # Check if the result contains an error (DocumentAgent returns error dict on failure, data dict on success)
        if "error" not in result:
            state.loan_data = result
            logging.info(f"Successfully pulled loan data!")
            logging.info(f"Has data object: {result.get('hasDataObject', 'N/A')}")
            logging.info(f"Raw response keys: {list(result.keys())}")
            
            # Log some key borrower information if available
            if '_raw_response' in result and 'dataObject' in result['_raw_response']:
                data_obj = result['_raw_response']['dataObject']
                if 'borrowers' in data_obj and data_obj['borrowers']:
                    borrower = data_obj['borrowers'][0]
                    logging.info(f"Borrower: {borrower.get('firstName', 'N/A')} {borrower.get('lastName', 'N/A')}")
                    logging.info(f"SSN: ***-**-{borrower.get('last4SSN', 'N/A')}")
            
            state.status = "Success"
        else:
            logging.error(f"Failed to pull loan data: {result.get('error', 'Unknown error')}")
            logging.error(f"Full API response: {result}")  # Log the full response for debugging
            state.status = "Error"
            state.loan_data = {"error": result.get("error", "Unknown error")}
        
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
                # Pull data for each document using user input values
                result = await asyncio.to_thread(
                    doc_agent.ESFuse.pull_data,
                    client_id=state.client_id,
                    loan_id=state.loan_id,
                    doc_id=str(doc_id),
                    esfuse_token=ESFUSE_TOKEN,
                    get_api_url=API_BASE_URL
                )
                
                # Extract PDF URL from response and download the PDF
                pdf_url = None
                if "error" not in result and "_raw_response" in result:
                    raw_response = result["_raw_response"]
                    if "url" in raw_response:
                        pdf_url = raw_response["url"]
                        logging.info(f"Found PDF URL for document {doc_id}: {pdf_url}")
                
                # Download PDF using the URL from response
                pdf_result = None
                if pdf_url:
                    try:
                        import requests
                        pdf_response = await asyncio.to_thread(requests.get, pdf_url, timeout=30)
                        if pdf_response.status_code == 200:
                            # Save PDF file locally
                            pdf_filename = f"{doc_id}.pdf"
                            def write_pdf_file(filename, content):
                                with open(filename, 'wb') as f:
                                    f.write(content)
                            
                            await asyncio.to_thread(write_pdf_file, pdf_filename, pdf_response.content)
                            pdf_result = {
                                "success": True,
                                "response_type": "pdf",
                                "filename": pdf_filename,
                                "file_size": len(pdf_response.content)
                            }
                            logging.info(f"Downloaded PDF document {doc_id} to {pdf_filename}")
                        else:
                            pdf_result = {
                                "success": False,
                                "error": f"Failed to download PDF: HTTP {pdf_response.status_code}"
                            }
                            logging.warning(f"Failed to download PDF for document {doc_id}: HTTP {pdf_response.status_code}")
                    except Exception as e:
                        pdf_result = {
                            "success": False,
                            "error": f"Exception downloading PDF: {str(e)}"
                        }
                        logging.warning(f"Exception downloading PDF for document {doc_id}: {str(e)}")
                else:
                    pdf_result = {
                        "success": False,
                        "error": "No PDF URL found in response"
                    }
                    logging.warning(f"No PDF URL found for document {doc_id}")
                
                if "error" not in result:
                    # Extract only the dataObject.fields from the raw response
                    raw_response = result.get("_raw_response", {})
                    data_object = raw_response.get("dataObject", {})
                    extracted_fields = data_object.get("fields", {})
                    
                    clean_result = {
                        "doc_id": doc_id,
                        "extracted_fields": extracted_fields  # Only the extracted data fields
                    }
                    
                    all_documents_data.append(clean_result)
                    logging.info(f"Successfully pulled data for document {doc_id}")
                    

                    
                    # Log PDF download result
                    if pdf_result and "success" in pdf_result and pdf_result["success"]:
                        if pdf_result.get("response_type") == "pdf":
                            logging.info(f"Downloaded PDF document {doc_id} to {pdf_result.get('filename', 'unknown')}")
                        else:
                            logging.info(f"Document {doc_id} data retrieved (JSON format)")
                    else:
                        logging.warning(f"Failed to download PDF for document {doc_id}: {pdf_result.get('error', 'Unknown error') if pdf_result else 'No result'}")
                    
                else:
                    logging.error(f"Failed to pull data for document {doc_id}: {result.get('error')}")
                    all_documents_data.append({
                        "doc_id": doc_id,
                        "error": result.get("error", "Unknown error")
                    })
            
            # Create the final output structure
            output_data = {
                "loan_id": state.loan_id,
                "client_id": state.client_id,
                "task_id": state.task_id,
                "status": state.status,
                "total_documents": len(doc_ids),
                "successful_pulls": len([doc for doc in all_documents_data if "error" not in doc]),
                "failed_pulls": len([doc for doc in all_documents_data if "error" in doc]),
                "documents": all_documents_data,
                "timestamp": str(datetime.datetime.now())
            }
            

            
            # Store the documents data in state for use by push_data_node
            state.documents_stored_list = all_documents_data
            state.loan_data = output_data
            state.status = "Success"
        else:
            state.status = "Error"
            state.loan_data = {"error": "No document_ids provided"}
        
        state.current_node = 2
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
        # Use environment variables for all configuration
        field_updates = {"example_field": "example_value"}  # Default field updates
        encompass_loan_guid = ENCOMPASS_LOAN_GUID
        base_url = API_BASE_URL
        access_token = ESFUSE_TOKEN
        
        logging.info(f"Pushing field updates for loan GUID: {encompass_loan_guid}")
        logging.info(f"Fields to update: {list(field_updates.keys())}")
        
        # Push data using DocumentAgent - wrap in asyncio.to_thread to avoid blocking
        result = await asyncio.to_thread(
            doc_agent.ESFuse.push_data,
            field_updates,
            encompass_loan_guid,
            base_url,
            access_token
        )
        
        # Check if the result contains an error
        if "error" not in result:
            state.loan_data = result
            logging.info(f"Successfully pushed field updates to Encompass")
            logging.info(f"Fields updated: {result.get('fields_updated', [])}")
            logging.info(f"Status code: {result.get('status_code', 'N/A')}")
            state.status = "Success"
        else:
            logging.error(f"Failed to push field updates: {result.get('error', 'Unknown error')}")
            logging.error(f"Full API response: {result}")
            state.status = "Error"
            state.loan_data = {"error": result.get("error", "Unknown error")}
        
        state.current_node = 3
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
        # Require these values from user input
        if not state.loan_id:
            logging.error("loan_id is required from user input")
            state.status = "Error"
            state.loan_data = {"error": "loan_id is required from user input"}
            state.current_node = 4
            return state
            
        if not state.document_ids:
            logging.error("document_ids is required from user input")
            state.status = "Error"
            state.loan_data = {"error": "document_ids is required from user input"}
            state.current_node = 4
            return state
        
        loan_id = state.loan_id
        document_ids = state.document_ids
        base_url = API_BASE_URL
        access_token = ESFUSE_TOKEN
        submission_type = SUBMISSION_TYPE
        auto_lock = AUTO_LOCK
        
        # Parse document_ids if it's a JSON string
        if isinstance(document_ids, str):
            try:
                import json
                document_ids = json.loads(document_ids)
            except json.JSONDecodeError:
                document_ids = [document_ids]
        
        logging.info(f"Creating submission for loan_id: {loan_id}")
        logging.info(f"Document IDs: {document_ids}")
        logging.info(f"Submission type: {submission_type}")
        logging.info(f"Auto lock: {auto_lock}")
        
        # Push document using DocumentAgent - wrap in asyncio.to_thread to avoid blocking
        result = await asyncio.to_thread(
            doc_agent.ESFuse.push_doc,
            loan_id=int(loan_id),
            document_ids=document_ids,
            base_url=base_url,
            access_token=access_token,
            submission_type=submission_type,
            auto_lock=auto_lock
        )
        
        # Check if the result contains an error
        if "error" not in result:
            state.loan_data = result
            logging.info(f"Successfully created loan submission")
            logging.info(f"Loan ID: {result.get('loan_id', 'N/A')}")
            logging.info(f"Document IDs: {result.get('document_ids', [])}")
            logging.info(f"Submission type: {result.get('submission_type', 'N/A')}")
            state.status = "Success"
        else:
            logging.error(f"Failed to create submission: {result.get('error', 'Unknown error')}")
            logging.error(f"Full API response: {result}")
            state.status = "Error"
            state.loan_data = {"error": result.get("error", "Unknown error")}
        
        state.current_node = 4
        return state
        
    except Exception as e:
        logging.error(f"Error in push_doc_node: {e}")
        state.current_node = 4
        state.status = "Error"
        state.loan_data = {"error": str(e)}
        return state



# =============================================================================
# GRAPH COMPILATION
# Define and compile your workflow graph here
# =============================================================================

# Define your graph here - customize as needed
graph = (
    StateGraph(State)
    .add_node("extract_input", extract_input_fields)
    .add_node("pull_data", pull_data_node)
    .add_node("pull_doc", pull_doc_node)
    
    .add_edge("__start__", "extract_input")
    .add_edge("extract_input", "pull_data")
    .add_edge("pull_data", "pull_doc")
    .add_edge("pull_doc", "__end__")
    # .add_edge("push_data", "__end__")

    # .add_edge("push_data", "push_doc")
    # .add_edge("push_doc", "__end__")
    .compile(
        name="lgCreditReportUnited",
    )
)


# curl -X GET "https://fllvck48n4.execute-api.us-west-1.amazonaws.com/prod/loan?clientId=loan_25&loanId=25" -H "Authorization: Bearer esfuse-token"

# curl -X GET "https://m49lxh6q5d.execute-api.us-west-1.amazonaws.com/prod/doc?clientId=loan_25&docId=953" -H "Authorization: Bearer esfuse-token"

