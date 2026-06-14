from channels.generic.websocket import AsyncWebsocketConsumer
import json
import redis

redis_client = redis.Redis(
    host='127.0.0.1',
    port=6379,
    db=0,
    decode_responses=True
)

class ChatConsumer(AsyncWebsocketConsumer):
        
    async def connect(self):
        print("USER CONNECTED")
        self.room_group_name = "chat_room"
        
        #Join group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Get recent messages
        messages = redis_client.lrange("chat_messages", 0, 9)
        
        for message in reversed(messages):
            await self.send(text_data=message)
            
        username = self.scope["query_string"].decode()
        
        # Add user to online users set
        redis_client.sadd("online_users", username)
        
        # Get current online count
        online_count = redis_client.scard("online_users")    
        
        # Broadcast online count
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "user_count",
                "count": online_count
            }
        )
        
    async def disconnect(self, close_code):
        username = self.scope["query_string"].decode()
        
        # Remove user   
        redis_client.srem("online_users", username)
        
        #Updated count
        online_count = redis_client.scard("online_users")
        
        # Broadcast updated count
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "user_count",
                "count": online_count
            }
        )
        
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
            )
        
    async def receive(self, text_data):
        print(f"MESSAGE RECEIVED {text_data}")
        data = json.loads(text_data)
        
        message = data["message"]
        username = data["username"]
        
        # Save message to Redis
        redis_client.lpush(
            "chat_messages",json.dumps({
                "username": username,
                "message": message
            })
        )
        
        # Keep only latest 50 messages
        redis_client.itrim("chat_messages", 0, 49)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message,
                "username": username,
            }
        )
        
    async def chat_message(self, event):
        message = event["message"]
        username = event["username"]
        await self.send(text_data=json.dumps({
            "message": message,
            "username": username,
        }))    
        
    async def user_count(self, event):
        await self.send(text_data=json.dumps({
            "online_users": event["count"]
        }))
    
        
        #Frontend sends message
        #        ↓
        #receive()
        #        ↓
        #group_send()  🔥
        #        ↓
        #chat_message() (runs for EVERY user)
        #        ↓
        #send() → frontend
        
        