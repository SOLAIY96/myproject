from rest_framework.generics import ListAPIView
from rest_framework.filters import SearchFilter
 
from .models import Post
from .serializers import PostSerializer
    
class PostLitsView(ListAPIView):
    filter_backends = [SearchFilter]
    search_fields = ["title", "content"]
    queryset = (
        Post.objects
        .prefetch_related("comments")
    )
    
    serializer_class = PostSerializer
