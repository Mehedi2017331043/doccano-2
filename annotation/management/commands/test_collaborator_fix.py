from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.test import RequestFactory
from annotation.models import Project, Text, Annotation, Label, ProjectCollaborator
from annotation.views import text_annotate
import json

class Command(BaseCommand):
    help = 'Test that collaborator annotations are visible across users'

    def handle(self, *args, **options):
        self.stdout.write("Testing collaborator annotation visibility...")

        # Clean up any existing test data
        User.objects.filter(username__in=['owner', 'collab1', 'collab2']).delete()

        # Create test users
        owner = User.objects.create_user(username='owner', password='test123')
        collaborator1 = User.objects.create_user(username='collab1', password='test123')
        collaborator2 = User.objects.create_user(username='collab2', password='test123')

        # Create a project
        project = Project.objects.create(
            name='Test Project',
            description='Testing annotation visibility',
            owner=owner
        )

        # Add collaborators
        ProjectCollaborator.objects.create(project=project, user=collaborator1)
        ProjectCollaborator.objects.create(project=project, user=collaborator2)

        # Create a label
        label = Label.objects.create(
            name='TEST_LABEL',
            color='#FF0000',
            project=project,
            created_by=owner
        )

        # Create a text
        text = Text.objects.create(
            project=project,
            text_id='test-text-1',
            text='This is a test sentence for annotation visibility testing.'
        )

        # Create annotations by different users
        annotation1 = Annotation.objects.create(
            text=text,
            user=owner,
            label=label,
            start_index=10,
            end_index=15,
            suggestions=['suggestion from owner']
        )

        annotation2 = Annotation.objects.create(
            text=text,
            user=collaborator1,
            label=label,
            start_index=20,
            end_index=25,
            suggestions=['suggestion from collaborator1']
        )

        annotation3 = Annotation.objects.create(
            text=text,
            user=collaborator2,
            label=label,
            start_index=30,
            end_index=35,
            suggestions=['suggestion from collaborator2']
        )

        self.stdout.write(f"Created {Annotation.objects.count()} annotations")

        # Test the view with different users
        factory = RequestFactory()

        # Test owner can see all annotations
        request = factory.get(f'/project/{owner.id}/{project.user_project_id}/text/{text.id}/')
        request.user = owner

        response = text_annotate(request, owner.id, project.user_project_id, text.id)
        annotations_data = response.context_data['annotations']

        self.stdout.write(f"Owner can see {len(annotations_data)} annotations")
        for ann in annotations_data:
            self.stdout.write(f"  - Annotation by {ann.user.username}: '{ann.annotated_text}'")

        # Test collaborator1 can see all annotations
        request = factory.get(f'/project/{owner.id}/{project.user_project_id}/text/{text.id}/')
        request.user = collaborator1

        response = text_annotate(request, owner.id, project.user_project_id, text.id)
        annotations_data = response.context_data['annotations']

        self.stdout.write(f"Collaborator1 can see {len(annotations_data)} annotations")
        for ann in annotations_data:
            self.stdout.write(f"  - Annotation by {ann.user.username}: '{ann.annotated_text}'")

        # Test collaborator2 can see all annotations
        request = factory.get(f'/project/{owner.id}/{project.user_project_id}/text/{text.id}/')
        request.user = collaborator2

        response = text_annotate(request, owner.id, project.user_project_id, text.id)
        annotations_data = response.context_data['annotations']

        self.stdout.write(f"Collaborator2 can see {len(annotations_data)} annotations")
        for ann in annotations_data:
            self.stdout.write(f"  - Annotation by {ann.user.username}: '{ann.annotated_text}'")

        # Verify all users can see all annotations
        expected_count = 3
        if len(annotations_data) == expected_count:
            self.stdout.write(self.style.SUCCESS(f"✅ SUCCESS: All users can see all {expected_count} annotations!"))

            # Test JSON data includes user information
            self.stdout.write("\nTesting JSON data includes user information...")

            annotations_json = response.context_data['annotations_json']
            json_data = json.loads(annotations_json)

            all_have_user_info = True
            for ann_data in json_data:
                if 'user_id' in ann_data and 'username' in ann_data:
                    self.stdout.write(f"✅ Annotation {ann_data['id']} has user_id: {ann_data['user_id']}, username: {ann_data['username']}")
                else:
                    self.stdout.write(f"❌ Annotation {ann_data['id']} missing user information")
                    all_have_user_info = False

            if all_have_user_info:
                self.stdout.write(self.style.SUCCESS("\n🎉 All tests passed! The collaborator annotation visibility issue has been fixed."))
            else:
                self.stdout.write(self.style.ERROR("\n💥 JSON data test failed."))
        else:
            self.stdout.write(self.style.ERROR(f"❌ FAILURE: Expected {expected_count} annotations, but got {len(annotations_data)}"))

        # Clean up
        User.objects.filter(username__in=['owner', 'collab1', 'collab2']).delete()