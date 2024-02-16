from django.http import HttpResponse, JsonResponse
from django_filters.rest_framework.backends import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
import django_filters
from rest_framework.filters import SearchFilter

from back.apps.language_model.models.data import (
    KnowledgeBase,
    KnowledgeItem,
    AutoGeneratedTitle,
    Intent, KnowledgeItemImage, DataSource,
)
from back.apps.language_model.serializers.data import (
    KnowledgeBaseSerializer,
    KnowledgeItemSerializer,
    AutoGeneratedTitleSerializer,
    IntentSerializer, KnowledgeItemImageSerializer, DataSourceSerializer,
)

from back.apps.language_model.tasks import (
    generate_suggested_intents_task,
    generate_intents_task,
    generate_titles,
)


class KnowledgeBaseAPIViewSet(viewsets.ModelViewSet):
    queryset = KnowledgeBase.objects.all()
    serializer_class = KnowledgeBaseSerializer

    def get_queryset(self):
        if self.kwargs.get("pk"):
            kb = KnowledgeBase.objects.filter(name=self.kwargs["pk"]).first()
            if kb:
                self.kwargs["pk"] = str(kb.pk)
        return super().get_queryset()

    @action(detail=True, url_name="download-csv", url_path="download-csv")
    def download_csv(self, request, *args, **kwargs):
        """
        A view to download all the knowledge base's items as a csv file:
        """
        kb = KnowledgeBase.objects.filter(name=kwargs["pk"]).first()
        if not kb:
            kb = KnowledgeBase.objects.get(pk=kwargs["pk"])
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename={}".format(
            kb.name + ".csv"
        )
        response.write(kb.to_csv())
        return response

    @action(
        detail=True, url_name="list-intents", url_path="list-intents", methods=["POST"]
    )
    def list_intents(self, request, *args, **kwargs):
        """
        A view to list all the intents for a Knowledge Base:
        """
        kb = KnowledgeBase.objects.filter(name=kwargs["pk"]).first()
        if not kb:
            return HttpResponse("Knowledge Base not found", status=404)
        existing = request.data["existing"] if "existing" in request.data else False
        suggested = request.data["suggested"] if "suggested" in request.data else False
        intents = []
        if existing:
            existing_intents = (
                Intent.objects.filter(
                    knowledge_item__knowledge_base=kb, suggested_intent=False
                )
                .distinct()
                .order_by("updated_date")
            )
            intents.extend(existing_intents)
        if suggested:
            suggested_intents = (
                Intent.objects.filter(
                    message__messageknowledgeitem__knowledge_item__knowledge_base=kb, suggested_intent=True
                )
                .distinct()
                .order_by("updated_date")
            )
            intents.extend(suggested_intents)
        serializer = IntentSerializer(intents, many=True)
        return JsonResponse(serializer.data, safe=False)


class KnowledgeItemFilterSet(django_filters.FilterSet):
    class Meta:
        model = KnowledgeItem
        fields = {
           'knowledge_base__id': ['exact'],
           'knowledge_base__name': ['exact'],
           'created_date': ['lte', 'gte'],
        }


class KnowledgeItemAPIViewSet(viewsets.ModelViewSet):
    queryset = KnowledgeItem.objects.all()
    serializer_class = KnowledgeItemSerializer

    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['title', 'content']
    filterset_class = KnowledgeItemFilterSet

    def create(self, request, *args, **kwargs):
        """
        A view to create a new knowledge item:
        """
        return super().create(request, *args, **kwargs)

    @action(
        detail=True, url_name="list-titles", url_path="list-titles", methods=["GET"]
    )
    def list_auto_gen_titles(self, request, *args, **kwargs):
        """
        A view to list all the auto generated titles for a knowledge item:
        """
        titles = AutoGeneratedTitle.objects.filter(
            knowledge_item__id=kwargs["pk"]
        ).all()
        serializer = AutoGeneratedTitleSerializer(titles, many=True)
        return JsonResponse(serializer.data, safe=False)

    @action(detail=True, url_name='list-intents', url_path='list-intents', methods=['GET'])
    def list_intents(self, request, *args, **kwargs):
        """
        A view to list all the intents for a knowledge item:
        """
        intents = Intent.objects.filter(knowledge_item__id=kwargs['pk']).all()
        serializer = IntentSerializer(intents, many=True)
        return JsonResponse(serializer.data, safe=False)


class KnowledgeItemImageAPIViewSet(viewsets.ModelViewSet):
    queryset = KnowledgeItemImage.objects.all()
    serializer_class = KnowledgeItemImageSerializer


class AutoGeneratedTitleAPIViewSet(viewsets.ModelViewSet):
    queryset = AutoGeneratedTitle.objects.all()
    serializer_class = AutoGeneratedTitleSerializer
    filterset_fields = ["knowledge_item__id"]

    @action(detail=True, url_name="generate", url_path="generate", methods=["POST"])
    def generate_titles(self, request, *args, **kwargs):
        """
        A view to generate titles for a Knowledge Base:
        """
        kb = KnowledgeBase.objects.filter(name=kwargs["pk"]).first()
        if not kb:
            return HttpResponse("Knowledge Base not found", status=404)
        n_titles = request.data["n_titles"] if "n_titles" in request.data else 10
        generate_titles.delay(kb.id, n_titles)
        return JsonResponse({"message": "Task started"})


class IntentFilterSet(django_filters.FilterSet):
    knowledge_base__id = django_filters.CharFilter(method='filter_knowledge_base__id')

    def filter_knowledge_base__id(self, queryset, name, value):
        return queryset.filter(knowledge_item__knowledge_base__id=value).distinct()

    class Meta:
        model = Intent
        fields = "__all__"


class IntentAPIViewSet(viewsets.ModelViewSet):
    queryset = Intent.objects.all()
    serializer_class = IntentSerializer
    search_fields = ['intent_name']
    filterset_class = IntentFilterSet
    filter_backends = [DjangoFilterBackend, SearchFilter]


    @action(
        detail=True,
        url_name="suggest-intents",
        url_path="suggest-intents",
        methods=["POST"],
    )
    def suggest_intents(self, request, *args, **kwargs):
        """
        A view to get suggested intents for a Knowledge Base:
        """
        kb = KnowledgeBase.objects.filter(name=kwargs["pk"]).first()
        if not kb:
            return HttpResponse("Knowledge Base not found", status=404)
        # if no AutoGeneratedTitle return error
        if not AutoGeneratedTitle.objects.filter(
            knowledge_item__knowledge_base=kb
        ).exists():
            return HttpResponse(
                "No auto generated titles found, create them first", status=404
            )

        generate_suggested_intents_task.delay(kb.id)
        return JsonResponse({"message": "Task started"})

    @action(
        detail=True,
        url_name="generate-intents",
        url_path="generate-intents",
        methods=["POST"],
    )
    def generate_intents(self, request, *args, **kwargs):
        """
        A view to generate intents from a Knowledge Base:
        """
        kb = KnowledgeBase.objects.filter(name=kwargs["pk"]).first()
        if not kb:
            return HttpResponse("Knowledge Base not found", status=404)
        # if no AutoGeneratedTitle return error
        if not AutoGeneratedTitle.objects.filter(
            knowledge_item__knowledge_base=kb
        ).exists():
            return HttpResponse(
                "No auto generated titles found, create them first", status=404
            )

        generate_intents_task.delay(kb.id)
        return JsonResponse({"message": "Task started"})

    @action(detail=True, url_name="list-knowledge-items", url_path="list-knowledge-items", methods=["GET"])
    def list_knowledge_items(self, request, *args, **kwargs):
        """
        A view to list all the knowledge items for an intent:
        """
        intent = Intent.objects.filter(id=kwargs["pk"]).first()
        if not intent:
            return HttpResponse("Intent not found", status=404)
        knowledge_items = KnowledgeItem.objects.filter(intent=intent).all()
        serializer = KnowledgeItemSerializer(knowledge_items, many=True)
        return JsonResponse(serializer.data, safe=False)


class DataSourceAPIViewSet(viewsets.ModelViewSet):
    queryset = DataSource.objects.all()
    serializer_class = DataSourceSerializer
