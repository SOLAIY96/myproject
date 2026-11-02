import graphene
from graphene_django import DjangoObjectType
from library.models import Task


class TaskType(DjangoObjectType):
    class Meta:
        model = Task
        fields = "__all__"


class Query(graphene.ObjectType):
    hello = graphene.String()
    tasks = graphene.List(TaskType)

    def resolve_hello(root, info):
        return "Hello, GraphQL!"

    def resolve_tasks(root, info):
        user = info.context.user

        if user.is_anonymous:
            return Task.objects.none()

        return Task.objects.filter(owner=user)


class CreateTask(graphene.Mutation):
    class Arguments:
        title = graphene.String(required=True)

    task = graphene.Field(TaskType)

    @classmethod
    def mutate(cls, root, info, title):
        user = info.context.user

        if user.is_anonymous:
            raise Exception("Authentication required")

        task = Task.objects.create(
            owner=user,
            title=title,
        )

        return CreateTask(task=task)


class Mutation(graphene.ObjectType):
    create_task = CreateTask.Field()


schema = graphene.Schema(
    query=Query,
    mutation=Mutation,
)
