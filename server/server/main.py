import os
import uvicorn
import uuid
import pdb
from fastapi import FastAPI, File, HTTPException, Depends, Body, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import urlparse
from services.sync_service import SyncService
from logger import Logger

from models.api import (
    AuthorizationResponse,
    AuthorizeOauthRequest,
    EnableConnectorRequest,
    ConnectorStatusRequest,
    ConnectorStatusResponse,
    GetDocumentsRequest,
    GetDocumentsResponse,
    GetConversationsRequest,
    GetConversationsResponse,
    AuthorizeApiKeyRequest,
    GetConnectionsRequest,
    GetConnectionsResponse,
    RunSyncRequest,
    RunSyncResponse,
)

from appstatestore.statestore import StateStore
from models.models import (
    AppConfig,
    DataConnector,
)
from connectors.connector_utils import get_connector_for_id, get_document_connector_for_id, get_conversation_connector_for_id
import uuid
from logger import Logger
logger = Logger()


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to the list of allowed origins if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer_scheme = HTTPBearer()



def validate_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    app_config = StateStore().get_config(credentials.credentials)
    if credentials.scheme != "Bearer" or app_config is None:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    return app_config

def validate_public_key(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    app_config = StateStore().get_config_from_public_key(credentials.credentials)
    if credentials.scheme != "Bearer" or app_config is None:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    return app_config


@app.post(
    "/set-custom-connector-credentials",
    response_model=ConnectorStatusResponse,
)
async def enable_connector(
    request: EnableConnectorRequest = Body(...),
    config: AppConfig = Depends(validate_token),
):
    try:
        connector_id = request.connector_id
        credential = request.credential
        status = StateStore().enable_connector(connector_id, credential, config)
        response = ConnectorStatusResponse(status=status)
        logger.log_api_call(config, 'set_custom_connector_credentials', request, response, False)
        return response
    except Exception as e:
        logger.log_api_call(config, 'set_custom_connector_credentials', request, e, True)
        raise e

@app.post(
    "/get-connector-status",
    response_model=ConnectorStatusResponse,
)
async def get_connector_status(
    request: ConnectorStatusRequest = Body(...),
    config: AppConfig = Depends(validate_token),
):
    try:
        connector_id = request.connector_id
        status = StateStore().get_connector_status(connector_id, config)
        response = ConnectorStatusResponse(status=status)
        logger.log_api_call(config, 'get_connector_status', request, response, False)
        return response
    except Exception as e:
        logger.log_api_call(config, 'get_connector_status', request, e, True)
        raise e

@app.post(
    "/get-connections",
    response_model=GetConnectionsResponse,
)
async def get_connections(
    request: GetConnectionsRequest = Body(...),
    config: AppConfig = Depends(validate_token),
):
    try:
        filter = request.filter
        connections = StateStore().get_connections(filter, config)
        response = GetConnectionsResponse(connections=connections)
        logger.log_api_call(config, 'get_connections', request, response, False)
        return response
    except Exception as e:
        logger.log_api_call(config, 'get_connections', request, e, True)
        raise e

@app.post(
    "/add-apikey-connection",
    response_model=AuthorizationResponse,
)
async def add_apikey_connection(
    request: AuthorizeApiKeyRequest = Body(...),
    config: AppConfig = Depends(validate_public_key),
):
    try:
        connector_id = request.connector_id
        connection_id = request.connection_id
        credential = request.credential
        metadata = request.metadata

        connector = get_connector_for_id(connector_id, config)

        if connector is None:
            raise HTTPException(status_code=404, detail="Connector not found")
        result = await connector.authorize_api_key(connection_id, credential, metadata)
        response = AuthorizationResponse(result=result)
        logger.log_api_call(config, 'add_apikey_connection', request, response, False)
        return response
    except Exception as e:
        logger.log_api_call(config, 'add_apikey_connection', request, e, True)
        raise e


@app.post(
    "/add-oauth-connection",
    response_model=AuthorizationResponse,
)
async def add_oauth_connection(
    request: AuthorizeOauthRequest = Body(...),
    config: AppConfig = Depends(validate_public_key),
):
    try:
        auth_code = request.auth_code or None
        connector_id = request.connector_id
        connection_id = request.connection_id
        metadata = request.metadata

        connector = get_connector_for_id(connector_id, config)

        print("connector", connector)

        if connector is None:
            raise HTTPException(status_code=404, detail="Connector not found")

        result = await connector.authorize(connection_id, auth_code, metadata)
        response = AuthorizationResponse(result=result)
        logger.log_api_call(config, 'add_oauth_connection', request, response, False)
        return response
    except Exception as e:
        logger.log_api_call(config, 'add_oauth_connection', request, e, True)
        raise e

@app.post(
    "/get-documents",
    response_model=GetDocumentsResponse,
)
async def get_documents(
    request: GetDocumentsRequest = Body(...),
    config: AppConfig = Depends(validate_token),
):
    try:
        connector_id = request.connector_id
        connection_id = request.connection_id

        connector = get_document_connector_for_id(connector_id, config)

        print("connector", connector)

        if connector is None:
            raise HTTPException(status_code=404, detail="Connector not found")

        result = await connector.load(connection_id)
        response = GetDocumentsResponse(documents=result)
        logger.log_api_call(config, 'get_documents', request, response, False)
        return response
    except Exception as e:
        logger.log_api_call(config, 'get_documents', request, e, True)
        raise e

@app.post(
    "/get-conversations",
    response_model=GetConversationsResponse,
)
async def get_conversations(
    request: GetConversationsRequest = Body(...),
    config: AppConfig = Depends(validate_token),
):
    try:
        connector_id = request.connector_id
        connection_id = request.connection_id
        oldest_timestamp = request.oldest_timestamp

        connector = get_conversation_connector_for_id(connector_id, config)

        print("connector", connector)

        if connector is None:
            raise HTTPException(status_code=404, detail="Connector not found")

        result = await connector.load(connection_id=connection_id, oldest_message_time=oldest_timestamp)
        response = GetConversationsResponse(conversations=result)
        logger.log_api_call(config, 'get_conversations', request, response, False)
        return response
    except Exception as e:
        logger.log_api_call(config, 'get_conversations', request, e, True)
        raise e

@app.post(
    "/run-sync",
    response_model=RunSyncResponse,
)
async def run_sync(
    request: RunSyncRequest = Body(...),
    config: AppConfig = Depends(validate_token),
):
    try:
        sync_all = request.sync_all
        success = await SyncService(config).run(sync_all=sync_all)
        response = RunSyncResponse(success=success)
        logger.log_api_call(config, 'run_sync', request, response, False)
        return response
    except Exception as e:
        logger.log_api_call(config, 'run_sync', request, e, True)
        raise e

def start():
    uvicorn.run("server.main:app", host="0.0.0.0", port=8080, reload=True)
