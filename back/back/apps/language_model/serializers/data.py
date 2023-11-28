import csv

from rest_framework import serializers

from back.apps.language_model.models.data import KnowledgeBase, KnowledgeItem, AutoGeneratedTitle, Intent
from django.forms import ModelForm
from django.forms.utils import ErrorList


class KnowledgeBaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeBase
        fields = "__all__"

    # extra step when validating CSVs: the file must contain the following columns: title, content, url
    def validate(self, data):
        title_index, content_index, url_index = data["title_index_col"], data["content_index_col"], data["url_index_col"]
        if data['original_csv'] is not None:
            f = data["original_csv"]
            decoded_file = f.read().decode("utf-8").splitlines()
            reader = csv.reader(decoded_file)
            next(reader) if data["csv_header"] else None
            mandatory_columns = [title_index, content_index, url_index]
            for _i, row in enumerate(reader):
                if len(row) < max(mandatory_columns):
                    raise serializers.ValidationError(
                        f"Row {_i + 1} does not contain all the required columns: {', '.join(str(i) for i in mandatory_columns)}"
                    )
                if not all(row[i].strip() for i in mandatory_columns):
                    raise serializers.ValidationError(
                        f"Row {_i + 1} does not contain all the required columns: {', '.join(str(i) for i in mandatory_columns)}"
                    )
            f.seek(0)
        return data

    def to_internal_value(self, data):
        if "id" in data:
            kb = KnowledgeBase.objects.filter(name=id).first()
            if kb:
                data["knowledge_base"] = kb.id
        return super().to_internal_value(data)


class KnowledgeBaseForm(ModelForm):
    class Meta:
        model = KnowledgeBase
        fields = "__all__"

    def is_valid(self):

        # Call super's is_valid to populate cleaned_data and do basic field validation
        valid = super(KnowledgeBaseForm, self).is_valid()
        if not valid:
            return False

        serializer = KnowledgeBaseSerializer(data=self.cleaned_data)
        if not serializer.is_valid():
            for field in serializer.errors:
                _field = field if field != "non_field_errors" else "original_csv"
                errors = self._errors.setdefault(_field, ErrorList())
                for e in serializer.errors[field]:
                    errors.append(e)
            return False
        return True


class KnowledgeBaseFromUrlSerializer(KnowledgeBaseSerializer):
    url = serializers.URLField()

    class Meta:
        model = KnowledgeBase
        fields = ["name", "lang", "url"]


class KnowledgeItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeItem
        fields = "__all__"

    def to_internal_value(self, data):
        if "knowledge_base" in data:
            kb = KnowledgeBase.objects.filter(name=data["knowledge_base"]).first()
            if kb:
                data["knowledge_base"] = str(kb.pk)
        return super().to_internal_value(data)


class AutoGeneratedTitleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutoGeneratedTitle
        fields = "__all__"        


class IntentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Intent
        fields = "__all__"

    def to_internal_value(self, data):
        if "knowledge_base" in data:
            kb = KnowledgeBase.objects.filter(name=data["knowledge_base"]).first()
            if kb:
                data["knowledge_base"] = str(kb.pk)
        return super().to_internal_value(data)
