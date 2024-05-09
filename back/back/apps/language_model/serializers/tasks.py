from rest_framework import serializers
from django_celery_results.models import TaskResult


class TaskResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskResult
        fields = "__all__"


class RayTaskSerializer(serializers.Serializer):
    task_id = serializers.CharField()
    attempt_number = serializers.IntegerField()
    name = serializers.CharField()
    state = serializers.CharField()
    job_id = serializers.CharField()
    actor_id = serializers.CharField()
    type = serializers.CharField()
    func_or_class_name = serializers.CharField()
    parent_task_id = serializers.CharField()
    node_id = serializers.CharField()
    worker_id = serializers.CharField()
    worker_pid = serializers.IntegerField()
    error_type = serializers.CharField()
    language = serializers.CharField()
    required_resources = serializers.DictField()
    runtime_env_info = serializers.DictField()
    placement_group_id = serializers.CharField()
    events = serializers.ListField()
    profiling_data = serializers.DictField()
    creation_time_ms = serializers.IntegerField()
    start_time_ms = serializers.IntegerField()
    end_time_ms = serializers.IntegerField()
    task_log_info = serializers.DictField()
    error_message = serializers.CharField()
