from django.http import JsonResponse
from django.shortcuts import render
from django.core.cache import cache
from .models import Post,Message
from asgiref.sync import sync_to_async
import asyncio  
import httpx

def get_messages_sync(request):
    messages = list(Message.objects.values())
    return JsonResponse({"data": messages})

async def get_message_async(requset):
    message = await sync_to_async(list)(Message.objects.values())
    return JsonResponse({"data": message})

def get_post_sync(request):
    post = list(Post.objects.values())
    return JsonResponse({"data": post})

async def get_post_async(request):
    cache_key = "post_list"
        
    # Try cache first
    data = cache.get(cache_key)
    
    if data:
        return JsonResponse({
            "source": "cache",
            "data": data
        })
    
    # Simulate slow operation
    await asyncio.sleep(2)
    
    # Fetch DB data
    post = await sync_to_async(list)(Post.objects.values())
    
    # Fetch external API
    async with httpx.AsyncClient() as client:
        response = await client.get("https://jsonplaceholder.typicode.com/posts")
        api_data = response.json()[:3]
        
    result = {
        "db_posts": post,
        "api_post": api_data
    }
    
    #save to cache (VERY IMPORTANT)
    cache.set(cache_key, result, timeout=60)
    
    return JsonResponse({
        "source": "db",
        "data": result
    })
    
    
    
def chat(request):
    return render(request, "chat.html")