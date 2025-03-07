import websockets
import json
import asyncio
from urllib.parse import urlparse
import socket
import logging
import ssl
import subprocess
import platform

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class HomeAssistantClient:
    def __init__(self, ws_url=None, access_token=None, is_nabu_casa=False):
        if ws_url:
            parsed_url = urlparse(ws_url)
            self.host = parsed_url.hostname
            self.port = parsed_url.port or 8123
            self.is_nabu_casa = is_nabu_casa
            self.ws_url = f"{ws_url}/api/websocket"
            logger.debug(f"Initialized HomeAssistantClient with URL: {self.ws_url}")
        else:
            self.ws_url = None
        self.access_token = access_token
        self.connection = None
        self.message_id = 1

    def _ping_host(self):
        """Test if host responds to ping"""
        try:
            param = '-n' if platform.system().lower() == 'windows' else '-c'
            command = ['ping', param, '1', self.host]
            logger.debug(f"Attempting to ping {self.host}")
            subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            return True
        except subprocess.TimeoutExpired:
            logger.error(f"Ping timeout for {self.host}")
            return False
        except Exception as e:
            logger.error(f"Ping failed: {str(e)}")
            return False

    def _check_host_connectivity(self):
        """Test basic connectivity to the host"""
        if self.is_nabu_casa:
            return True, None

        try:
            # First try ping
            if not self._ping_host():
                error_msg = (f"Cannot ping {self.host}. Please verify:\n"
                           f"1. The IP address/hostname is correct\n"
                           f"2. Home Assistant is running\n"
                           f"3. You are on the same network (for local connections)\n"
                           f"4. No firewall is blocking the connection")
                return False, error_msg

            logger.debug(f"Attempting TCP connection to {self.host}:{self.port}")
            sock = socket.create_connection((self.host, self.port), timeout=5)
            sock.close()
            logger.debug("TCP connection successful")
            return True, None

        except socket.gaierror:
            error_msg = f"Could not resolve hostname {self.host}. Please check the URL."
            logger.error(error_msg)
            return False, error_msg
        except socket.timeout:
            error_msg = f"Connection to {self.host}:{self.port} timed out."
            logger.error(error_msg)
            return False, error_msg
        except ConnectionRefusedError:
            error_msg = f"Connection refused on {self.host}:{self.port}. Please verify Home Assistant is running."
            logger.error(error_msg)
            return False, error_msg
        except socket.error as e:
            error_msg = (f"Network error connecting to {self.host}:{self.port}\n"
                        f"Error: {str(e)}\n"
                        f"Please verify:\n"
                        f"1. The URL is correct\n"
                        f"2. Home Assistant is running\n"
                        f"3. You are on the same network (for local connections)\n"
                        f"4. No firewall is blocking the connection")
            logger.error(f"TCP connection failed: {str(e)}")
            return False, error_msg

    async def _test_connection_async(self):
        try:
            # Check basic connectivity first
            can_connect, error_msg = self._check_host_connectivity()
            if not can_connect:
                return False, error_msg

            logger.debug(f"Attempting WebSocket connection to {self.ws_url}")
            
            # Create SSL context if needed
            ssl_context = None
            if self.is_nabu_casa or self.ws_url.startswith('wss://'):
                ssl_context = ssl.create_default_context()
                if not self.is_nabu_casa:
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE

            # Connect to WebSocket
            async with websockets.connect(
                self.ws_url,
                ssl=ssl_context,
                close_timeout=5,
                ping_interval=None  # Disable ping to speed up test
            ) as websocket:
                logger.debug("WebSocket connection established")
                
                try:
                    # Wait for auth_required message
                    auth_required = await asyncio.wait_for(websocket.recv(), timeout=5)
                    auth_required_data = json.loads(auth_required)
                    logger.debug(f"Received initial message: {auth_required_data}")
                    
                    if auth_required_data["type"] != "auth_required":
                        return False, "Unexpected response from Home Assistant"
                    
                    # Send auth message
                    auth_message = {
                        "type": "auth",
                        "access_token": self.access_token
                    }
                    await websocket.send(json.dumps(auth_message))
                    logger.debug("Sent authentication message")
                    
                    # Wait for auth response
                    auth_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                    auth_response_data = json.loads(auth_response)
                    logger.debug(f"Received auth response: {auth_response_data}")
                    
                    if auth_response_data["type"] == "auth_ok":
                        return True, None
                    elif auth_response_data["type"] == "auth_invalid":
                        return False, "Invalid access token"
                    else:
                        return False, "Unexpected authentication response"
                
                except asyncio.TimeoutError:
                    return False, "Connection timed out. Please check your Home Assistant URL and network connection."
                
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False, str(e)

    def test_connection(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self._test_connection_async())
        except Exception as e:
            error_message = str(e)
            logger.error(f"Connection test failed: {error_message}")
            return False, error_message

    async def connect(self):
        """Connect to the Home Assistant WebSocket."""
        if self.connection:
            await self.disconnect()
        
        # Create SSL context if needed
        ssl_context = None
        if self.is_nabu_casa or self.ws_url.startswith('wss://'):
            ssl_context = ssl.create_default_context()
            if not self.is_nabu_casa:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
        
        # Connect to WebSocket
        self.connection = await websockets.connect(
            self.ws_url,
            ssl=ssl_context,
            close_timeout=5
        )
        
        # Wait for auth_required message
        auth_required = await self.connection.recv()
        
        # Send auth message
        auth_message = {
            "type": "auth",
            "access_token": self.access_token
        }
        await self.connection.send(json.dumps(auth_message))
        
        # Wait for auth response
        auth_response = await self.connection.recv()
        auth_response_data = json.loads(auth_response)
        
        if auth_response_data["type"] != "auth_ok":
            await self.disconnect()
            raise Exception("Authentication failed")

    async def send_command(self, domain, service, entity_id):
        message = {
            "type": "call_service",
            "domain": domain,
            "service": service,
            "target": {
                "entity_id": entity_id
            }
        }
        await self.connection.send(json.dumps(message))

    async def get_entities(self):
        if not self.connection:
            await self.connect()
        
        message = {
            "id": 1,
            "type": "get_states"
        }
        await self.connection.send(json.dumps(message))
        response = await self.connection.recv()
        response_data = json.loads(response)
        
        if not response_data.get("success", True):
            error = response_data.get("error", {})
            error_msg = error.get("message", "Unknown error")
            logger.error(f"Error getting states: {error_msg}")
            raise Exception(f"Failed to get states: {error_msg}")
        
        entities = response_data.get("result", [])
        
        # Define supported domains
        supported_domains = ['light', 'sensor', 'climate', 'vacuum', 'cover']
        
        # Format and filter entities for frontend
        formatted_entities = []
        for entity in entities:
            if 'entity_id' in entity:
                domain = entity['entity_id'].split('.')[0]
                if domain in supported_domains:
                    formatted_entities.append({
                        'entity_id': entity['entity_id'],
                        'name': entity.get('attributes', {}).get('friendly_name', entity['entity_id']),
                        'domain': domain
                    })
        
        # Sort entities by domain and name
        return sorted(formatted_entities, key=lambda x: (x['domain'], x['name']))

    async def disconnect(self):
        """Disconnect from the Home Assistant WebSocket."""
        if self.connection:
            try:
                await self.connection.close()
            except Exception as e:
                logger.error(f"Error disconnecting: {str(e)}")
            finally:
                self.connection = None

    async def get_entity_states(self, entity_ids):
        """Get states for specific entity IDs."""
        if not self.connection:
            await self.connect()
        
        message = {
            "id": 1,
            "type": "get_states"
        }
        await self.connection.send(json.dumps(message))
        response = await self.connection.recv()
        response_data = json.loads(response)
        
        if not response_data.get("success", True):
            error = response_data.get("error", {})
            error_msg = error.get("message", "Unknown error")
            logger.error(f"Error getting states: {error_msg}")
            raise Exception(f"Failed to get states: {error_msg}")
        
        # Create a dictionary of entity states
        states = {}
        for state in response_data.get("result", []):
            if state['entity_id'] in entity_ids:
                states[state['entity_id']] = state
        
        return states

    async def update_config(self, new_url=None, new_token=None):
        """Update the client configuration with new URL and/or token."""
        if new_url:
            parsed_url = urlparse(new_url)
            self.host = parsed_url.hostname
            self.port = parsed_url.port or 8123
            self.ws_url = f"{new_url}/api/websocket"
        
        if new_token:
            self.access_token = new_token

        # Test the new configuration
        success, error = await self._test_connection_async()
        if not success:
            # Revert changes if connection test fails
            raise Exception(f"Failed to connect with new configuration: {error}")

        return True

    async def validate_entities(self, entity_ids):
        """Validate that the given entity IDs exist and are accessible."""
        if not self.connection:
            await self.connect()
        
        states = await self.get_entity_states(entity_ids)
        valid_entities = []
        invalid_entities = []
        
        for entity_id in entity_ids:
            if entity_id in states:
                valid_entities.append(entity_id)
            else:
                invalid_entities.append(entity_id)
        
        return {
            'valid': valid_entities,
            'invalid': invalid_entities
        }
    # Calendar Events Functions
    async def get_calendar_events(self, start_date=None, end_date=None, limit=10):
        """Fetch calendar events from Home Assistant."""
        if not self.connection:
            await self.connect()
        
        # Get list of calendar entities first
        message_id = self.message_id
        self.message_id += 1
        
        message = {
            "id": message_id,
            "type": "get_states"
        }
        await self.connection.send(json.dumps(message))
        response = await self.connection.recv()
        response_data = json.loads(response)
        
        if not response_data.get("success", True):
            error = response_data.get("error", {})
            error_msg = error.get("message", "Unknown error")
            logger.error(f"Error getting states: {error_msg}")
            raise Exception(f"Failed to get states: {error_msg}")
        
        entities = response_data.get("result", [])
        
        # Filter for calendar entities
        calendar_entities = []
        for entity in entities:
            if 'entity_id' in entity and entity['entity_id'].startswith('calendar.') or entity['entity_id'].startswith('calendar.bin'):
                calendar_entities.append(entity['entity_id'])
        
        if not calendar_entities:
            logger.info("No calendar entities found")
            return []
        
        # Now request calendar events for each calendar entity
        all_events = []
        for entity_id in calendar_entities:
            message_id = self.message_id
            self.message_id += 1
            
            # Prepare service data with optional date parameters
            service_data = {}
            if start_date:
                service_data["start_date_time"] = start_date
            if end_date:
                service_data["end_date_time"] = end_date
                    
            # Create message for calling the calendar service with return_response at top-level
            message = {
                "id": message_id,
                "type": "call_service",
                "domain": "calendar",
                "service": "get_events",
                "target": {
                    "entity_id": entity_id
                },
                "service_data": service_data,
                "return_response": True  # Moved here at the top level
            }
            
            logger.debug(f"Getting calendar events for {entity_id} with message: {message}")
                
            await self.connection.send(json.dumps(message))
            response = await self.connection.recv()
            response_data = json.loads(response)
            logger.debug(f"Received calendar events response: {response_data}")
            if not response_data.get("success", True):
                error = response_data.get("error", {})
                error_msg = error.get("message", "Unknown error")
                logger.error(f"Error getting calendar events: {error_msg}")
                continue
            
            try:
                # Get the response field which contains the calendar data
                response_field = response_data.get("result", {}).get("response", {})
                
                # Get events for the specific calendar entity
                calendar_events = response_field.get(entity_id, {}).get("events", [])
                
                # Add calendar name to each event
                calendar_name = entity_id.replace('calendar.', '').replace('_', ' ').title()
                for event in calendar_events:
                    event['calendar_name'] = calendar_name
                    event['calendar_id'] = entity_id
                
                all_events.extend(calendar_events)
                logger.debug(f"Extracted {len(calendar_events)} events from {entity_id}")
            
            except Exception as e:
                logger.error(f"Error parsing calendar events: {str(e)}")
                logger.debug(f"Response data: {response_data}")
        
        # Sort events by start time
        all_events.sort(key=lambda e: e.get('start', ''))
        
        # Limit the number of events if requested
        if limit and len(all_events) > limit:
            all_events = all_events[:limit]
        
        logger.debug(f"Returning {len(all_events)} total calendar events")
        return all_events