from django.db import models


class AdministrativeLevel(models.Model):
    """Defines hierarchical administrative levels like Country, Region, District"""

    name = models.CharField(max_length=100, unique=True)
    order = models.PositiveIntegerField(help_text="Defines the level in hierarchy (e.g., 1 for Country, 2 for Region)", unique=True)

    class Meta:
        ordering = ['order']
        unique_together = ('name', 'order')

    def __str__(self):
        return self.name


class AdministrativeUnit(models.Model):
    """Represents an administrative division (e.g., Ghana, Accra Region, etc.)"""

    name = models.CharField(max_length=200)
    level = models.ForeignKey(AdministrativeLevel, on_delete=models.CASCADE, related_name="units")
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name="children")
    hierarchy_name = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'parent'],
                name='unique_name_per_parent',
                condition=models.Q(parent__isnull=False),
            ),
            models.UniqueConstraint(
                fields=['name'],
                name='unique_root_name',
                condition=models.Q(parent__isnull=True),
            ),
        ]

    @classmethod
    def get_descendant_ids(cls, root_ids):
        """Return all descendant ids (inclusive of the roots) for the given units.

        Walks the tree one hierarchy level at a time, so the number of queries is
        bounded by the depth of the tree (~4-5) instead of one query per node as a
        naive ``node.children.all()`` recursion would do. ``parent_id`` is an
        indexed FK, so each level is a single cheap lookup.
        """
        ids = set(root_ids)
        frontier = list(ids)
        while frontier:
            children = [
                child_id
                for child_id in cls.objects.filter(parent_id__in=frontier).values_list('id', flat=True)
                if child_id not in ids
            ]
            ids.update(children)
            frontier = children
        return ids

    def save(self, *args, **kwargs):
        self.hierarchy_name = self.__get_hierarchy_name(self)
        super().save(*args, **kwargs)

    @classmethod
    def __get_hierarchy_name(cls, administrative_unit):
        if administrative_unit.parent is None:
            return "{} {}".format(administrative_unit.level.name, administrative_unit.name)
        return "{} {}, {}".format(administrative_unit.level.name, administrative_unit.name,
                                  cls.__get_hierarchy_name(administrative_unit.parent))

    def __str__(self):
        return f"{self.name} ({self.level.name})"
