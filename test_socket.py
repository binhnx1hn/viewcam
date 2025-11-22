"""
Test file for Socket.IO client
Tests the use_socket_statical functionality
"""
import time
import json
from hooks.use_socket import use_socket_statical, SocketClient
from department_mapping import get_department_name, get_department_area, get_department_info


def test_message_handler(payload):
    """
    Example message handler callback
    This function will be called when messages are received
    """
    print(f"\n[Message Received] {time.strftime('%H:%M:%S')}")
    print(f"Payload type: {type(payload)}")
    
    # Handle different payload types
    if isinstance(payload, dict):
        # Enhance payload with department name and area if department_id exists
        if 'department_id' in payload:
            dept_id = payload['department_id']
            dept_info = get_department_info(dept_id)
            dept_name = dept_info.get('name', dept_id) if dept_info else dept_id
            dept_area = dept_info.get('area', '') if dept_info else ''
            
            payload_display = payload.copy()
            payload_display['department_name'] = dept_name
            if dept_area:
                payload_display['department_area'] = dept_area
            
            print(f"Department: {dept_name}")
            if dept_area:
                print(f"Area: {dept_area}")
            print(f"ID: {dept_id}")
            if 'data_count' in payload:
                counts = payload['data_count']
                print(f"Counts:")
                print(f"  - Prisoner: {counts.get('prisoner', 0)}")
                print(f"  - Officer: {counts.get('officer', 0)}")
                print(f"  - Relative: {counts.get('relative', 0)}")
            print(f"Full payload: {json.dumps(payload_display, indent=2, ensure_ascii=False)}")
        else:
            print(f"Payload (dict): {json.dumps(payload, indent=2, ensure_ascii=False)}")
    elif isinstance(payload, str):
        try:
            # Try to parse as JSON
            parsed = json.loads(payload)
            print(f"Payload (JSON string): {json.dumps(parsed, indent=2, ensure_ascii=False)}")
        except json.JSONDecodeError:
            print(f"Payload (string): {payload}")
    else:
        print(f"Payload: {payload}")


def test_basic_connection():
    """Test basic socket connection"""
    print("=" * 60)
    print("Test 1: Basic Connection")
    print("=" * 60)
    
    # Create socket client with default options
    client = use_socket_statical(test_message_handler)
    
    try:
        # Connect to server
        from hooks.use_socket import SOCKET_URL
        print(f"Connecting to: {SOCKET_URL}")
        client.connect()
        
        # Wait for connection
        time.sleep(2)
        
        if client.is_connected:
            print("✓ Connection successful!")
        else:
            print("✗ Connection failed!")
        
        # Keep connection alive for testing
        print("\nListening for messages... (Press Ctrl+C to stop)")
        print("Waiting 5 seconds for messages...")
        time.sleep(5)
        
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        client.disconnect()
        print("Disconnected")


def test_custom_options():
    """Test socket connection with custom options"""
    print("\n" + "=" * 60)
    print("Test 2: Custom Options")
    print("=" * 60)
    
    options = {
        'roomId': 'test-room-123',
        'username': 'Python_Test_Client',
        'eventName': 'test-event'
    }
    
    client = use_socket_statical(test_message_handler, options)
    
    try:
        print(f"Room ID: {client.room_id}")
        print(f"Username: {client.username}")
        print(f"Event Name: {client.event_name}")
        
        client.connect()
        time.sleep(2)
        
        if client.is_connected:
            print("✓ Connection successful with custom options!")
        else:
            print("✗ Connection failed!")
        
        print("\nWaiting 5 seconds for messages...")
        time.sleep(5)
        
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        client.disconnect()
        print("Disconnected")


def test_context_manager():
    """Test socket client using context manager"""
    print("\n" + "=" * 60)
    print("Test 3: Context Manager Usage")
    print("=" * 60)
    
    try:
        with use_socket_statical(test_message_handler) as client:
            print(f"Connected: {client.is_connected}")
            print("Waiting 5 seconds for messages...")
            time.sleep(5)
        # Automatically disconnected when exiting context
        print("✓ Context manager closed connection")
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    except Exception as e:
        print(f"\nError: {e}")


def test_update_options():
    """Test updating options dynamically"""
    print("\n" + "=" * 60)
    print("Test 4: Update Options Dynamically")
    print("=" * 60)
    
    client = use_socket_statical(test_message_handler)
    
    try:
        client.connect()
        time.sleep(2)
        
        if client.is_connected:
            print("✓ Initial connection successful!")
            
            # Wait a bit
            time.sleep(2)
            
            # Update options
            print("\nUpdating room ID and username...")
            client.update_options({
                'roomId': 'new-room-456',
                'username': 'Updated_Client'
            })
            
            print(f"New Room ID: {client.room_id}")
            print(f"New Username: {client.username}")
            
            print("\nWaiting 5 seconds for messages...")
            time.sleep(5)
        else:
            print("✗ Connection failed!")
        
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        client.disconnect()
        print("Disconnected")


def main():
    """Main test function"""
    print("\n" + "=" * 60)
    print("Socket.IO Client Test Suite")
    print("=" * 60)
    print("\nAvailable tests:")
    print("1. Basic Connection")
    print("2. Custom Options")
    print("3. Context Manager")
    print("4. Update Options Dynamically")
    print("5. Run All Tests")
    print("0. Exit")
    
    while True:
        try:
            choice = input("\nSelect test (0-5): ").strip()
            
            if choice == '0':
                print("Exiting...")
                break
            elif choice == '1':
                test_basic_connection()
            elif choice == '2':
                test_custom_options()
            elif choice == '3':
                test_context_manager()
            elif choice == '4':
                test_update_options()
            elif choice == '5':
                test_basic_connection()
                test_custom_options()
                test_context_manager()
                test_update_options()
                print("\n" + "=" * 60)
                print("All tests completed!")
                print("=" * 60)
            else:
                print("Invalid choice. Please select 0-5.")
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"\nError: {e}")


if __name__ == "__main__":
    main()

