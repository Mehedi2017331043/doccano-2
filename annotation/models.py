from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Project(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_projects')
    user_project_id = models.PositiveIntegerField(editable=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.pk:  # Only for new projects
            # Get the maximum user_project_id for this owner and add 1
            max_id = Project.objects.filter(owner=self.owner).aggregate(models.Max('user_project_id'))['user_project_id__max']
            self.user_project_id = (max_id or 0) + 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        owner_id = self.owner_id
        super().delete(*args, **kwargs)
        # After deletion, renumber all remaining projects for this owner
        projects = Project.objects.filter(owner_id=owner_id).order_by('created_at')
        for index, project in enumerate(projects, start=1):
            project.user_project_id = index
            super(Project, project).save(update_fields=['user_project_id'])

    def __str__(self):
        return self.name

class Label(models.Model):
    name = models.CharField(max_length=255)
    color = models.CharField(max_length=7, default='#000000')  # Hex color
    description = models.TextField(blank=True)
    is_static = models.BooleanField(default=False)  # Admin fixed labels
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='labels')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ('name', 'project')

    def __str__(self):
        return self.name

class Text(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='texts')
    text_id = models.CharField(max_length=255, blank=True)  # Main data id
    text = models.TextField()  # Main text/sentence
    meta = models.JSONField(default=dict)  # For additional data
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Doc {self.id}: {self.text[:50]}..."

class Annotation(models.Model):
    text = models.ForeignKey(Text, on_delete=models.CASCADE, related_name='annotations')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='annotations')
    label = models.ForeignKey(Label, on_delete=models.CASCADE)
    start_index = models.IntegerField()
    end_index = models.IntegerField()
    suggestions = models.JSONField(default=list, blank=True)  # List of strings
    is_reannotation = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('text', 'user', 'start_index', 'end_index', 'label')

    def __str__(self):
        return f"Annotation by {self.user.username} on {self.text}"

class ProjectCollaborator(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='collaborators')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collaborations')
    added_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('project', 'user')

    def __str__(self):
        return f"{self.user.username} in {self.project.name}"