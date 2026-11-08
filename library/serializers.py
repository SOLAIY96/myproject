from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Attachment, Comment, Notification, Post, Task

User = get_user_model()


class TaskSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source="owner.username")

    class Meta:
        model = Task
        fields = ["id", "title", "completed", "owner"]

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError("Task title cannot be empty.")

        return value.strip()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email"),
            password=validated_data["password"],
        )
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)

    new_password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
    )


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = "__all__"


class PostSerializer(serializers.ModelSerializer):
    comments = CommentSerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = ["id", "title", "created_at", "comments"]


class AttachmentSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source="owner.username")

    class Meta:
        model = Attachment
        fields = ["id", "file", "owner", "created_at"]
        read_only_fields = ["id", "owner", "created_at"]

    def validate_file(self, file):
        max_size = 5 * 1024 * 1024

        allowed_signatures = {
            ".pdf": b"%PDF-",
            ".jpg": b"\xff\xd8\xff",
            ".jpeg": b"\xff\xd8\xff",
            ".png": b"\x89PNG\r\n\x1a\n",
        }

        extension = Path(file.name).suffix.lower()

        if file.size > max_size:
            raise serializers.ValidationError("File must not exceed 5 MB.")

        if extension not in allowed_signatures:
            raise serializers.ValidationError(
                "Only PDF, JPEG, and PNG files are allowed."
            )

        # Inspect the actual file bytes, not just the browser's MIME type.
        try:
            file.seek(0)
            header = file.read(8)
        finally:
            file.seek(0)

        expected_signature = allowed_signatures[extension]

        if not header.startswith(expected_signature):
            raise serializers.ValidationError(
                "File contents do not match the allowed file type."
            )

        return file


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "message",
            "is_read",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "message",
            "created_at",
        ]
