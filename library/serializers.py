from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Comment, Post


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "emil"]


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = "__all__"


class PostSerializer(serializers.ModelSerializer):
    author = UserSerializer()
    comment = CommentSerializer(many=True)

    class Meta:
        model = Post
        fields = "__all__"
