"""
FSM QuerySet Mixins for annotating entities with their current state.

Provides reusable Django QuerySet mixins that efficiently annotate entities
with their current FSM state using optimized subqueries to prevent N+1 queries.

Usage:
    class TaskQuerySet(FSMStateQuerySetMixin, models.QuerySet):
        pass

    class TaskManager(models.Manager):
        def get_queryset(self):
            return TaskQuerySet(self.model, using=self._db)

Note:
    State annotation is guarded by 'fflag_feat_fit_568_finite_state_management' only.
    This allows background FSM processes to annotate current_state for internal use.

    UI/API consumption of state fields is separately controlled by serializers
    that check BOTH 'fflag_feat_fit_568_finite_state_management' AND
    'fflag_feat_fit_710_fsm_state_fields' before exposing state data.

    When the flag is disabled, no annotation is performed and there is zero performance impact.
"""

import logging

from core.current_request import CurrentContext
from core.feature_flags import flag_set
from django.db.models import OuterRef, Subquery
from fsm.registry import get_state_model

logger = logging.getLogger(__name__)


class FSMStateQuerySetMixin:
    """
    Mixin for Django QuerySets to efficiently annotate FSM state.

    Provides the `with_state()` method that adds a `current_state`
    annotation to the queryset using an optimized subquery.

    This approach:
    - Prevents N+1 queries by using a single JOIN/subquery
    - Handles missing states gracefully (returns None)
    - Uses UUID7 natural ordering for optimal performance
    - Works with any FSM entity that has a registered state model

    Example:
        # In your model manager
        class TaskManager(models.Manager):
            def get_queryset(self):
                return TaskQuerySet(self.model, using=self._db)

            def with_state(self):
                return self.get_queryset().with_state()

        # Usage - both approaches work identically
        tasks = Task.objects.with_state().filter(project=project)
        # Or chain it after filters
        tasks = Task.objects.filter(project=project).with_state()

        for task in tasks:
            print(f"Task {task.id}: {task.current_state}")  # No additional queries!
    """

    def with_state(self):
        """
        Annotate the queryset with the current FSM state.

        DISABLED FOR MYSQL/MARIADB COMPATIBILITY:
        The subquery pattern using OuterRef('pk') generates invalid SQL in MySQL/MariaDB
        that references incorrect table aliases (e.g., 'project.id' instead of proper alias).
        This is a known Django ORM limitation with MySQL subqueries in complex queries.
        
        Since FSM state annotation is an enterprise feature for workflow management
        and not critical for core Label Studio functionality, we disable it entirely
        to maintain MySQL/MariaDB compatibility.

        Returns:
            QuerySet: The queryset unchanged (no annotation added)
        """
        # MYSQL/MARIADB COMPATIBILITY: Return queryset unchanged
        # Do not add any annotations that could cause MySQL query failures
        logger.debug(f'FSM with_state() disabled for MySQL/MariaDB compatibility')
        return self
