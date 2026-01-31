from core.feature_flags import flag_set
from core.utils.db import SQCount
from django.db import connection
from django.db.models import Count, OuterRef, Q, Value
from django.db.models.functions import Coalesce
from tasks.models import Annotation, Prediction, Task


def annotate_task_number(queryset):
    # MYSQL/MARIADB COMPATIBILITY: OuterRef generates invalid SQL
    # Return dummy annotation with 0 to avoid breaking API contracts
    if connection.vendor == 'mysql':
        return queryset.annotate(task_number=Value(0))
    tasks = Task.objects.filter(project=OuterRef('id')).values_list('id')
    return queryset.annotate(task_number=SQCount(tasks))


def annotate_finished_task_number(queryset):
    if flag_set('fflag_fix_back_plt_811_finished_task_number_01072025_short', user='auto'):
        return queryset.annotate(finished_task_number=Count('tasks', filter=Q(tasks__is_labeled=True)))
    else:
        # MYSQL/MARIADB COMPATIBILITY: OuterRef generates invalid SQL
        # Return dummy annotation with 0 to avoid breaking API contracts
        if connection.vendor == 'mysql':
            return queryset.annotate(finished_task_number=Value(0))
        tasks = Task.objects.filter(project=OuterRef('id'), is_labeled=True).values_list('id')
        return queryset.annotate(finished_task_number=SQCount(tasks))


def annotate_total_predictions_number(queryset):
    # MYSQL/MARIADB COMPATIBILITY: OuterRef generates invalid SQL
    # Return dummy annotation with 0 to avoid breaking API contracts
    if connection.vendor == 'mysql':
        return queryset.annotate(total_predictions_number=Value(0))
    predictions = Prediction.objects.filter(project=OuterRef('id')).values('id')
    return queryset.annotate(total_predictions_number=SQCount(predictions))


def annotate_total_annotations_number(queryset):
    # MYSQL/MARIADB COMPATIBILITY: OuterRef generates invalid SQL
    # Return dummy annotation with 0 to avoid breaking API contracts
    if connection.vendor == 'mysql':
        return queryset.annotate(total_annotations_number=Value(0))
    subquery = Annotation.objects.filter(Q(project=OuterRef('pk')) & Q(was_cancelled=False)).values('id')
    return queryset.annotate(total_annotations_number=SQCount(subquery))


def annotate_num_tasks_with_annotations(queryset):
    # @todo: check do we really need this counter?
    # this function is very slow because of tasks__id and distinct
    # MYSQL/MARIADB COMPATIBILITY: OuterRef generates invalid SQL
    # Return dummy annotation with 0 to avoid breaking API contracts
    if connection.vendor == 'mysql':
        return queryset.annotate(num_tasks_with_annotations=Value(0))
    subquery = (
        Annotation.objects.filter(
            Q(project=OuterRef('pk')) & Q(ground_truth=False) & Q(was_cancelled=False) & Q(result__isnull=False)
        )
        .values('task__id')
        .distinct()
    )
    return queryset.annotate(num_tasks_with_annotations=SQCount(subquery))


def annotate_useful_annotation_number(queryset):
    # MYSQL/MARIADB COMPATIBILITY: OuterRef generates invalid SQL
    # Return dummy annotation with 0 to avoid breaking API contracts
    if connection.vendor == 'mysql':
        return queryset.annotate(useful_annotation_number=Value(0))
    subquery = Annotation.objects.filter(
        Q(project=OuterRef('pk')) & Q(was_cancelled=False) & Q(ground_truth=False) & Q(result__isnull=False)
    ).values('id')
    return queryset.annotate(useful_annotation_number=SQCount(subquery))


def annotate_ground_truth_number(queryset):
    # MYSQL/MARIADB COMPATIBILITY: OuterRef generates invalid SQL
    # Return dummy annotation with 0 to avoid breaking API contracts
    if connection.vendor == 'mysql':
        return queryset.annotate(ground_truth_number=Value(0))
    subquery = Annotation.objects.filter(Q(project=OuterRef('pk')) & Q(ground_truth=True)).values('id')
    return queryset.annotate(ground_truth_number=SQCount(subquery))


def annotate_skipped_annotations_number(queryset):
    # MYSQL/MARIADB COMPATIBILITY: OuterRef generates invalid SQL
    # Return dummy annotation with 0 to avoid breaking API contracts
    if connection.vendor == 'mysql':
        return queryset.annotate(skipped_annotations_number=Value(0))
    subquery = Annotation.objects.filter(Q(project=OuterRef('pk')) & Q(was_cancelled=True)).values('id')
    return queryset.annotate(skipped_annotations_number=SQCount(subquery))
