from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('project/create/', views.project_create, name='project_create'),
    path('project/<int:user_id>/<int:user_project_id>/detail/', views.project_detail, name='project_detail'),
    path('project/<int:user_id>/<int:user_project_id>/delete/', views.project_delete, name='project_delete'),
    path('project/<int:user_id>/<int:user_project_id>/import/', views.texts_import, name='texts_import'),
    path('project/<int:user_id>/<int:user_project_id>/labels/', views.project_labels, name='project_labels'),
    path('project/<int:user_id>/<int:user_project_id>/labels/create/', views.label_create, name='label_create'),
    path('project/<int:user_id>/<int:user_project_id>/labels/<int:label_id>/edit/', views.label_edit, name='label_edit'),
    path('project/<int:user_id>/<int:user_project_id>/labels/<int:label_id>/delete/', views.label_delete, name='label_delete'),
    path('project/<int:user_id>/<int:user_project_id>/collaborators/', views.project_collaborators, name='project_collaborators'),
    path('project/<int:user_id>/<int:user_project_id>/add_collaborator/', views.add_collaborator, name='add_collaborator'),
    path('project/<int:user_id>/<int:user_project_id>/remove_collaborator/<int:collaborator_user_id>/', views.remove_collaborator, name='remove_collaborator'),
    path('project/<int:user_id>/<int:user_project_id>/export/', views.export_annotations, name='export_annotations'),
    path('project/<int:user_id>/<int:user_project_id>/text/<int:text_id>/annotate/', views.text_annotate, name='text_annotate'),
    path('project/<int:user_id>/<int:user_project_id>/text/<int:text_id>/add_annotation/', views.add_annotation, name='add_annotation'),
    path('project/<int:user_id>/<int:user_project_id>/text/<int:text_id>/update_annotation/<int:annotation_id>/', views.update_annotation, name='update_annotation'),
    path('annotation/<int:annotation_id>/delete/', views.delete_annotation, name='delete_annotation'),
    # Add more URLs as we implement features
]
