from trackableobjects.models import FollowUpEventDependency


def build_dependency_map():
    """
    Return {child_follow_up_event_id: [parent_follow_up_event_name, ...]}.

    Shared by the relationship overview and its two HTMX detail partials so all
    three render "depends on" the same way, from a single query.
    """
    dependency_map = {}
    for dependency in FollowUpEventDependency.objects.select_related('parent', 'child'):
        dependency_map.setdefault(dependency.child_id, []).append(dependency.parent.name)
    return dependency_map
