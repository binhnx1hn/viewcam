"""
Socket.IO client hook equivalent for Python
Mimics the behavior of useSocketStatical React hook
"""
import os
import json
import socketio
from typing import Callable, Optional, Dict, Any


# Get socket URL from environment variable or use default
SOCKET_URL = os.getenv('VITE_INDENTIFY_WS', 'http://192.168.22.2:7882')


class SocketClient:
    """
    Python equivalent of useSocketStatical hook
    Manages Socket.IO connection, room joining, and event listening
    """
    
    def __init__(
        self,
        on_message: Callable[[Any], None],
        options: Optional[Dict[str, str]] = None
    ):
        """
        Initialize socket client
        
        Args:
            on_message: Callback function to handle incoming messages
            options: Optional dict with 'roomId', 'username', 'eventName'
        """
        self.on_message = on_message
        self.options = options or {}
        
        self.room_id = self.options.get('roomId', 'room-count-in-department')
        self.username = self.options.get('username', 'FE_CameraAI')
        self.event_name = self.options.get('eventName', 'broadcast-count-in-department')
        self.room_joined = 'room-count-in-department-joined'
        
        self.socket: Optional[socketio.Client] = None
        self.is_connected = False
        
        # Initialize socket connection
        self._setup_socket()
    
    def _setup_socket(self):
        """Setup Socket.IO client with event handlers"""
        self.socket = socketio.Client(
            reconnection=True,
            reconnection_delay=1,
            reconnection_attempts=5,
            logger=False,
            engineio_logger=False
        )
        
        # Connection event handlers
        @self.socket.on('connect')
        def on_connect():
            print('Socket Connected!')
            self.is_connected = True
            self._join_room()
        
        @self.socket.on('disconnect')
        def on_disconnect(reason=None):
            if reason:
                print(f'Socket Disconnected. Reason: {reason}')
            else:
                print('Socket Disconnected.')
            self.is_connected = False
        
        @self.socket.on('connect_error')
        def on_connect_error(error):
            print(f'Connection error: {error}')
        
        @self.socket.event
        def error(error):
            print(f'Socket error: {error}')
        
        # Room joined confirmation
        @self.socket.on(self.room_joined)
        def on_room_joined(response):
            print(f'Room joined confirmation: {response}')
        
        # Dynamic event listener for the specified event
        @self.socket.on(self.event_name)
        def on_event(payload):
            self.on_message(payload)
    
    def _join_room(self):
        """Join the specified room"""
        if not self.socket or not self.is_connected:
            return
        
        join_data = {
            'roomId': self.room_id,
            'username': self.username
        }
        self.socket.emit('join-room', json.dumps(join_data))
        print(f'Joined room: {self.room_id}')
    
    def connect(self):
        """Connect to the Socket.IO server"""
        if self.socket and not self.socket.connected:
            try:
                self.socket.connect(
                    SOCKET_URL,
                    socketio_path='/socket.io',
                    transports=['websocket']
                )
            except Exception as e:
                print(f'Failed to connect: {e}')
    
    def disconnect(self):
        """Disconnect from the Socket.IO server"""
        if self.socket and self.socket.connected:
            self.socket.disconnect()
            self.is_connected = False
    
    def update_options(self, options: Dict[str, str]):
        """
        Update roomId, username, or eventName and rejoin room if needed
        
        Args:
            options: Dict with 'roomId', 'username', or 'eventName' to update
        """
        room_changed = False
        username_changed = False
        
        if 'roomId' in options and options['roomId'] != self.room_id:
            self.room_id = options['roomId']
            room_changed = True
        
        if 'username' in options and options['username'] != self.username:
            self.username = options['username']
            username_changed = True
        
        if 'eventName' in options and options['eventName'] != self.event_name:
            # Unregister old event handler and register new one
            old_event = self.event_name
            self.event_name = options['eventName']
            
            # Note: socketio-python doesn't easily support dynamic event unregistration
            # We'll need to handle this differently
            # For now, we'll just update the event name
            # In a real scenario, you might need to recreate the socket connection
        
        # Rejoin room if roomId or username changed
        if (room_changed or username_changed) and self.is_connected:
            self._join_room()
            print(f'Re-joined room due to change: {self.room_id}')
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


def use_socket_statical(
    on_message: Callable[[Any], None],
    options: Optional[Dict[str, str]] = None
) -> SocketClient:
    """
    Factory function to create a SocketClient instance
    Similar to the React hook pattern
    
    Args:
        on_message: Callback function to handle incoming messages
        options: Optional dict with 'roomId', 'username', 'eventName'
    
    Returns:
        SocketClient instance
    """
    return SocketClient(on_message, options)

