from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.models import User
from django.db import transaction
from .models import Project, Label, Text, Annotation, ProjectCollaborator
from .forms import ProjectForm, LabelForm
from django.core.paginator import Paginator
import csv
import io
import json

def home(request):
    if request.user.is_authenticated:
        projects = Project.objects.filter(owner=request.user) | Project.objects.filter(collaborators__user=request.user)
        projects = projects.distinct()
        return render(request, 'home.html', {'projects': projects})
    return render(request, 'home.html')

@login_required
def project_create(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.owner = request.user
            project.save()
            # Create default labels for Bangla errors
            default_labels = [
                {'name': 'SUB_VERB_AGREEMENT_ERROR', 'error_code': 2, 'color': "#EA6B6B"},
                {'name': 'SADHU_CHALIT_MIX_ERROR', 'error_code': 4, 'color': "#69F869"},
                {'name': 'PUNCTUATION_ERROR', 'error_code': 8, 'color': "#8383E2"},
                {'name': 'NON_WORD_ERROR', 'error_code': 16, 'color': "#F1F14A"},
                {'name': 'UNKNOWN_WORD', 'error_code': 32, 'color': "#F455F4"},
                {'name': 'INFLECTION_ERROR', 'error_code': 64, 'color': '#00FFFF'},
                {'name': 'NO_SPACE_ERROR', 'error_code': 128, 'color': "#956F6F"},
                {'name': 'EXTAR_SPACE_ERROR', 'error_code': 256, 'color': "#41A441"},
                {'name': 'INAPPROPRIATE_WORD_USAGE_ERROR', 'error_code': 512, 'color': "#505A68"},
                {'name': 'PREPOSITION_CONJUNCTION_ERROR', 'error_code': 1024, 'color': "#8E8E45"},
                {'name': 'REPETITION_ERROR', 'error_code': 2048, 'color': "#985298"},
                {'name': 'QUALITY_SENTENCE_ERROR', 'error_code': 4096, 'color': "#389494"},
                {'name': 'REAL_WORD_ERROR', 'error_code': 8192, 'color': "#726969"},
            ]
            labels_created = 0
            for label_data in default_labels:
                try:
                    Label.objects.create(
                        name=label_data['name'],
                        error_code=label_data['error_code'],
                        color=label_data['color'],
                        project=project,
                        created_by=request.user,
                        is_static=True
                    )
                    labels_created += 1
                except Exception as e:
                    messages.warning(request, f'Failed to create label "{label_data["name"]}": {str(e)}')
            if labels_created > 0:
                messages.info(request, f'Created {labels_created} default labels for the project.')
            messages.success(request, 'Project created successfully!')
            return redirect('project_detail', user_id=request.user.id, user_project_id=project.user_project_id)
    else:
        form = ProjectForm()
    return render(request, 'project_create.html', {'form': form})

@login_required
def project_detail(request, user_id, user_project_id):
    project = get_object_or_404(Project, owner_id=user_id, user_project_id=user_project_id)
    if project.owner != request.user and not ProjectCollaborator.objects.filter(project=project, user=request.user).exists():
        messages.error(request, 'You do not have access to this project.')
        return redirect('home')

    labels = project.labels.all()

    # Get all texts with annotation status for current user
    texts_queryset = project.texts.all()

    # Add annotation status to each text
    texts_with_status = []
    for text in texts_queryset:
        # Show ALL annotations for this text, not just current user's annotations
        annotations = text.annotations.all().order_by('start_index')
        has_annotations = annotations.exists()
        annotation_count = annotations.count() if has_annotations else 0

        # Create JSON data for template filter
        annotations_data = []
        for ann in annotations:
            try:
                # Calculate annotated text from the text content
                annotated_text = text.text[ann.start_index:ann.end_index]
                annotations_data.append({
                    'id': ann.id,
                    'start_index': ann.start_index,
                    'end_index': ann.end_index,
                    'label': ann.label.name,
                    'label_color': ann.label.color,
                    'annotated_text': annotated_text,
                    'suggestions': ann.suggestions or []
                })
            except (IndexError, TypeError, AttributeError):
                continue
        try:
            annotations_json = json.dumps(annotations_data, ensure_ascii=False)
        except (TypeError, ValueError, UnicodeEncodeError):
            annotations_json = json.dumps([])
        texts_with_status.append({
            'text': text,
            'has_annotations': has_annotations,
            'annotation_count': annotation_count,
            'annotations_json': annotations_json
        })

    # Pagination - 20 texts per page

    page_number = request.GET.get('page', 1)
    paginator = Paginator(texts_with_status, 20)
    page_obj = paginator.get_page(page_number)

    # Check if user can manage this project (owner or collaborator)
    can_manage_project = (project.owner == request.user or
                        ProjectCollaborator.objects.filter(project=project, user=request.user).exists())

    return render(request, 'project_detail.html', {
        'project': project,
        'labels': labels,
        'page_obj': page_obj,
        'can_manage_project': can_manage_project
    })

@login_required
def project_delete(request, user_id, user_project_id):
    project = get_object_or_404(Project, owner_id=user_id, user_project_id=user_project_id)
    if project.owner != request.user:
        messages.error(request, 'Only the owner can delete the project.')
        return redirect('project_detail', user_id=user_id, user_project_id=user_project_id)
    if request.method == 'POST':
        project.delete()
        messages.success(request, 'Project deleted successfully!')
        return redirect('home')
    return render(request, 'project_delete.html', {'project': project})

@login_required
def project_labels(request, user_id, user_project_id):
    project = get_object_or_404(Project, owner_id=user_id, user_project_id=user_project_id)
    if project.owner != request.user and not ProjectCollaborator.objects.filter(project=project, user=request.user).exists():
        messages.error(request, 'You do not have access to this project.')
        return redirect('home')
    labels = project.labels.all().order_by('name')
    return render(request, 'project_labels.html', {
        'project': project,
        'labels': labels
    })

@login_required
def label_create(request, user_id, user_project_id):
    project = get_object_or_404(Project, owner_id=user_id, user_project_id=user_project_id)
    if project.owner != request.user and not ProjectCollaborator.objects.filter(project=project, user=request.user).exists():
        messages.error(request, 'You do not have access to create labels for this project.')
        return redirect('project_detail', user_id=project.owner.id, user_project_id=project.user_project_id)
    if request.method == 'POST':
        form = LabelForm(request.POST)
        if form.is_valid():
            label = form.save(commit=False)
            label.project = project
            label.created_by = request.user
            label.save()
            messages.success(request, f'Label "{label.name}" created successfully!')
            return redirect('project_labels', user_id=project.owner.id, user_project_id=project.user_project_id)
    else:
        form = LabelForm()
    return render(request, 'label_create.html', {
        'project': project,
        'form': form
    })

@login_required
def label_edit(request, user_id, user_project_id, label_id):
    project = get_object_or_404(Project, owner_id=user_id, user_project_id=user_project_id)
    if project.owner != request.user and not ProjectCollaborator.objects.filter(project=project, user=request.user).exists():
        messages.error(request, 'You do not have access to edit labels for this project.')
        return redirect('project_detail', user_id=project.owner.id, user_project_id=project.user_project_id)
    
    label = get_object_or_404(Label, id=label_id, project=project)
    
    if request.method == 'POST':
        form = LabelForm(request.POST, instance=label)
        if form.is_valid():
            form.save()
            messages.success(request, f'Label "{label.name}" updated successfully!')
            return redirect('project_labels', user_id=project.owner.id, user_project_id=project.user_project_id)
    else:
        form = LabelForm(instance=label)
        
    return render(request, 'label_edit.html', {
        'project': project,
        'label': label,
        'form': form
    })

@login_required
def label_delete(request, user_id, user_project_id, label_id):
    project = get_object_or_404(Project, owner_id=user_id, user_project_id=user_project_id)
    if project.owner != request.user and not ProjectCollaborator.objects.filter(project=project, user=request.user).exists():
        messages.error(request, 'You do not have access to delete labels for this project.')
        return redirect('project_detail', user_id=project.owner.id, user_project_id=project.user_project_id)
        
    label = get_object_or_404(Label, id=label_id, project=project)
    
    if request.method == 'POST':
        label_name = label.name
        label.delete()
        messages.success(request, f'Label "{label_name}" deleted successfully!')
        return redirect('project_labels', user_id=project.owner.id, user_project_id=project.user_project_id)
        
    return render(request, 'label_delete.html', {
        'project': project,
        'label': label
    })

@login_required
def texts_import(request, user_id, user_project_id):
    project = get_object_or_404(Project, owner_id=user_id, user_project_id=user_project_id)
    if project.owner != request.user:
        messages.error(request, 'Only the owner can import data.')
        return redirect('project_detail', user_id=project.owner.id, user_project_id=project.user_project_id)

    if request.method == 'POST':
        import_type = request.POST.get('import_type', 'single')

        try:
            with transaction.atomic():
                if import_type == 'dual':
                    # Dual file import
                    return _handle_dual_file_import(request, project)
                else:
                    # Single file import (existing functionality)
                    return _handle_single_file_import(request, project)

        except Exception as e:
            messages.error(request, f'Import failed: {str(e)}. All changes have been rolled back.')
            return render(request, 'texts_import.html', {'project': project})

    return render(request, 'texts_import.html', {'project': project})

def _handle_single_file_import(request, project):
    """Handle single file import (existing functionality)"""
    if not request.FILES.get('csv_file'):
        messages.error(request, 'No CSV file provided.')
        return redirect('project_detail', user_id=project.owner.id, user_project_id=project.user_project_id)

    csv_file = request.FILES['csv_file']

    # Try different encodings to handle various file formats
    encodings_to_try = ['utf-8-sig', 'utf-8', 'windows-1252', 'iso-8859-1', 'cp1252']
    decoded_file = None
    for encoding in encodings_to_try:
        try:
            csv_file.seek(0)  # Reset file pointer
            decoded_file = csv_file.read().decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if decoded_file is None:
        messages.error(request, 'Could not decode the CSV file. Please ensure it is properly encoded.')
        return redirect('project_detail', user_id=project.owner.id, user_project_id=project.user_project_id)
    
    io_string = io.StringIO(decoded_file)
    reader = csv.DictReader(io_string)
    
    if not reader.fieldnames:
        messages.error(request, 'CSV file is empty or missing headers.')
        return redirect('project_detail', user_id=project.owner.id, user_project_id=project.user_project_id)

    has_annotations = any(key in reader.fieldnames for key in ['start_index', 'error_label', 'suggestions'])
    imported_texts = 0
    imported_annotations = 0

    if has_annotations:
        # Import annotated data
        text_cache = {}  # Cache to avoid duplicate text creation

        for row in reader:
            try:
                # Get or create text
                input_text_id = row.get('input_text_id', row.get('ID', row.get('id', '')))
                content = row.get('content', row.get('Content', row.get('text', '')))

                if not content.strip():
                    continue

                # Ensure text is properly encoded and normalized
                if isinstance(content, str):
                    content = content.strip().replace('\x00', '').replace('\r', '')

                # Use input_text_id as key for caching
                text_key = input_text_id or content[:50]  # Fallback key

                if text_key not in text_cache:
                    text_obj, created = Text.objects.get_or_create(
                        project=project,
                        text_id=input_text_id if input_text_id else None,
                        defaults={'text': content}
                    )
                    if not created:
                        # Update existing text if content is different
                        if text_obj.text != content:
                            text_obj.text = content
                            text_obj.save()
                    text_cache[text_key] = text_obj
                    imported_texts += 1

                text_obj = text_cache[text_key]

                # Create annotation if annotation data exists
                start_index_str = row.get('start_index', '')
                error_label = row.get('error_label', '')
                suggestions = row.get('suggestions', '')

                if start_index_str and error_label:
                    try:
                        start_index = int(start_index_str)

                        # Get or create label
                        label, created = Label.objects.get_or_create(
                            project=project,
                            error_label=error_label,
                            defaults={
                                'color': "#444040",
                                'created_by': request.user
                            }
                        )

                        # Calculate end_index from annotated text if available
                        annotated_text = row.get('selected_sub_text', '')
                        if annotated_text:
                            end_index = start_index + len(annotated_text)
                        else:
                            # Estimate end_index based on context
                            end_index = start_index + 1

                        # Ensure end_index is within text bounds
                        if end_index > len(text_obj.text):
                            end_index = len(text_obj.text)

                        # Create annotation
                        Annotation.objects.get_or_create(
                            text=text_obj,
                            user=request.user,
                            start_index=start_index,
                            end_index=end_index,
                            label=label,
                            defaults={'suggestions': [s.strip() for s in suggestions.split(',') if s.strip()]}
                        )
                        imported_annotations += 1

                    except (ValueError, TypeError) as e:
                        messages.warning(request, f'Error importing annotation for row: {str(e)}')
                        continue

            except Exception as e:
                messages.warning(request, f'Error importing row: {str(e)}')
                continue

        messages.success(request, f'Successfully imported {imported_texts} texts and {imported_annotations} annotations!')

    else:
        # Plain text import (existing functionality)
        # Check if we can use optimized raw import for 2-column CSVs to preserve quotes
        fieldnames = reader.fieldnames if reader.fieldnames else []
        is_simple_csv = False
        
        # Identify ID and Content columns
        id_col_name = next((col for col in fieldnames if col.lower() in ['id', 'input_text_id']), None)
        text_col_name = next((col for col in fieldnames if col.lower() in ['text', 'content']), None)
        
        if id_col_name and text_col_name and len(fieldnames) == 2:
            is_simple_csv = True
            is_id_first = fieldnames.index(id_col_name) == 0
            
            # Reset file pointer to read raw lines
            io_string.seek(0)
            # Skip header
            next(io_string, None)
            
            for line in io_string:
                line = line.rstrip('\r\n')
                if not line: continue
                
                try:
                    # split only on the separator to preserve quotes in content
                    if is_id_first:
                        parts = line.split(',', 1)
                        if len(parts) < 2: continue
                        text_id = parts[0].strip()
                        text = parts[1]
                    else:
                        parts = line.rsplit(',', 1)
                        if len(parts) < 2: continue
                        text = parts[0]
                        text_id = parts[1].strip()
                    
                    # Remove null bytes for DB safety, but avoid other normalization
                    if isinstance(text, str):
                        text = text.replace('\x00', '')

                    Text.objects.create(
                        project=project,
                        text_id=text_id,
                        text=text,
                    )
                    imported_texts += 1
                except Exception as e:
                    # Log error but continue
                    print(f"Error importing row: {e}")
                    continue
        else:
            # Fallback to standard CSV reader for complex files
            for row in reader:
                try:
                    text_id = row.get('ID', row.get('id', ''))
                    text = row.get('Content', row.get('text', ''))
    
                    # Helper to clean text without stripping intentional whitespace
                    if not text:
                        continue
    
                    # Minimal cleanup: remove null bytes and carriage returns
                    if isinstance(text, str):
                        text = text.replace('\x00', '').replace('\r', '')
    
                    Text.objects.create(
                        project=project,
                        text_id=text_id,
                        text=text,
                    )
                    imported_texts += 1
                except Exception as e:
                    messages.warning(request, f'Error importing row: {str(e)}')
                    continue

        messages.success(request, f'Successfully imported {imported_texts} texts!')

    return redirect('project_detail', user_id=project.owner.id, user_project_id=project.user_project_id)

def _handle_dual_file_import(request, project):
    """Handle dual file import with atomic transaction"""
    # Validate required files
    text_csv_file = request.FILES.get('text_csv_file')
    annotation_csv_file = request.FILES.get('annotation_csv_file')

    if not text_csv_file:
        messages.error(request, 'Text CSV file is required for dual file import.')
        raise Exception('Missing text CSV file')
    if not annotation_csv_file:
        messages.error(request, 'Annotation CSV file is required for dual file import.')
        raise Exception('Missing annotation CSV file')

    imported_texts = 0
    imported_annotations = 0

    # Step 1: Import texts from first CSV
    text_mapping = _import_texts_from_csv(text_csv_file, project)
    imported_texts = len(text_mapping)

    # Step 2: Import annotations from second CSV if provided
    if annotation_csv_file:
        annotation_results = _import_annotations_from_csv(request, annotation_csv_file, project, text_mapping, request.user)
        imported_annotations = annotation_results['imported']
        duplicate_annotations = annotation_results['duplicates']

        if duplicate_annotations > 0:
            messages.info(request, f'Removed {duplicate_annotations} duplicate annotations.')

    if imported_annotations > 0:
        messages.success(request, f'Successfully imported {imported_texts} texts and {imported_annotations} annotations!')
    else:
        messages.success(request, f'Successfully imported {imported_texts} texts!')

    return redirect('project_detail', user_id=project.owner.id, user_project_id=project.user_project_id)

def _import_texts_from_csv(csv_file, project):
    """Import texts from CSV file and return mapping of text_id to Text object"""
    # Try different encodings to handle various file formats
    encodings_to_try = ['utf-8-sig', 'utf-8', 'windows-1252', 'iso-8859-1', 'cp1252']
    decoded_file = None
    for encoding in encodings_to_try:
        try:
            csv_file.seek(0)  # Reset file pointer
            decoded_file = csv_file.read().decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if decoded_file is None:
        raise Exception('Could not decode the text CSV file. Please ensure it is properly encoded.')

    io_string = io.StringIO(decoded_file)
    reader = csv.DictReader(io_string)
    cnt=0

    # Validate required columns
    sample_row = next(reader, None)
    if sample_row is None:
        raise Exception('Text CSV file is empty.')

    # Check for required columns
    has_id_column = any(col in sample_row for col in ['ID', 'id'])
    has_text_column = any(col in sample_row for col in ['Text', 'text', 'Content', 'content'])

    if not has_id_column:
        raise Exception('Text CSV must contain an ID column (ID or id).')
    if not has_text_column:
        raise Exception('Text CSV must contain a text content column (Text, text, or Content).')

    # Reset reader to beginning
    io_string.seek(0)
    reader = csv.DictReader(io_string)

    text_mapping = {}  # Maps text_id to Text object

    for row in reader:
        try:
            # Extract ID and text content
            text_id = row.get('ID', row.get('id', ''))
            text_content = row.get('content', row.get('text', row.get('Text', '')))

            if not text_content.strip():
                continue

            # Ensure text is properly encoded and normalized
            if isinstance(text_content, str):
                text_content = text_content.strip().replace('\x00', '').replace('\r', '')

            # Create or update text
            text_obj, created = Text.objects.get_or_create(
                project=project,
                text_id=text_id if text_id else None,
                defaults={'text': text_content}
            )

            if not created:
                # Update existing text if content is different
                if text_obj.text != text_content:
                    text_obj.text = text_content
                    text_obj.save()

            text_mapping[text_id] = text_obj

        except Exception as e:
            # Use print for testing, messages.warning in production
            print(f'Error importing text row: {str(e)}')
            continue

    return text_mapping

def _import_annotations_from_csv(request, csv_file, project, text_mapping, user):
    """Import annotations from CSV file and return import statistics"""
    # Try different encodings to handle various file formats
    encodings_to_try = ['utf-8', 'utf-8-sig', 'windows-1252', 'iso-8859-1', 'cp1252']
    decoded_file = None

    for encoding in encodings_to_try:
        try:
            csv_file.seek(0)  # Reset file pointer
            decoded_file = csv_file.read().decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if decoded_file is None:
        raise Exception('Could not decode the annotation CSV file. Please ensure it is properly encoded.')

    io_string = io.StringIO(decoded_file)
    reader = csv.DictReader(io_string)

    # Validate required columns
    sample_row = next(reader, None)
    if sample_row is None:
        return {'imported': 0, 'duplicates': 0}  # Empty file is OK

    # Check for required columns
    required_columns = ['input_text_id', 'content', 'start_index', 'error_cat']
    missing_columns = [col for col in required_columns if col not in sample_row]

    if missing_columns:
        raise Exception(f'Annotation CSV is missing required columns: {", ".join(missing_columns)}')

    # Reset reader to beginning
    io_string.seek(0)
    reader = csv.DictReader(io_string)

    imported_annotations = 0
    duplicate_annotations = 0

    # Track annotations to detect duplicates (same text, start_index, end_index)
    annotation_cache = {}  # Key: (text_id, start_index, end_index)

    for row in reader:
        try:
            input_text_id = row.get('input_text_id', '')
            content = row.get('content', '')
            start_index_str = row.get('start_index', '')
            error_cat = row.get('error_cat', '')
            corrections = row.get('corrections', '')

            if not input_text_id or not start_index_str or not error_cat:
                continue

            # Find the text object using the mapping
            text_obj = None
            for text_id, obj in text_mapping.items():
                if str(text_id) == str(input_text_id):
                    text_obj = obj
                    break

            if not text_obj:
                messages.warning(request, f'No text found with ID {input_text_id}. Skipping annotation.')
                continue

            try:
                start_index = int(start_index_str)
            except ValueError:
                messages.warning(request, f'Invalid start_index "{start_index_str}". Skipping annotation.')
                continue

            # Calculate end_index based on content length
            if content:
                end_index = start_index + len(content)
            else:
                # If no content, use start_index + 1 as fallback
                end_index = start_index + 1

            # Ensure indices are within text bounds
            if start_index < 0 or end_index > len(text_obj.text) or start_index >= end_index:
                messages.warning(request, f'Invalid text range {start_index}-{end_index} for text ID {input_text_id}. Skipping annotation.')
                continue

            # Check for duplicate annotations (same text, start_index, end_index)
            cache_key = (text_obj.id, start_index, end_index)
            if cache_key in annotation_cache:
                duplicate_annotations += 1
                continue

            # Get or create label
            label, created = Label.objects.get_or_create(
                project=project,
                error_code=error_cat,
                defaults={
                    'color': '#000000',
                    'created_by': user
                }
            )

            # Create annotation
            Annotation.objects.create(
                text=text_obj,
                user=user,
                start_index=start_index,
                end_index=end_index,
                label=label,
                suggestions=[corrections.strip()] if corrections.strip() else []
            )

            # Mark this annotation as imported to prevent duplicates
            annotation_cache[cache_key] = True
            imported_annotations += 1

        except Exception as e:
            # Use print for testing, messages.warning in production
            print(f'Error importing annotation row: {str(e)}')
            continue

    return {'imported': imported_annotations, 'duplicates': duplicate_annotations}

@login_required
def text_annotate(request, user_id, user_project_id, text_id):
    project = get_object_or_404(Project, owner_id=user_id, user_project_id=user_project_id)
    text = get_object_or_404(Text, id=text_id, project=project)
    if project.owner != request.user and not ProjectCollaborator.objects.filter(project=project, user=request.user).exists():
        messages.error(request, 'You do not have access to this text.')
        return redirect('project_detail', user_id=project.owner.id, user_project_id=project.user_project_id)

    # Clean and normalize text if it contains problematic characters or hyphens
    original_text = text.text
    try:
        # Test if the text can be properly handled
        text.text.encode('utf-8').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        # Clean the text by removing problematic characters
        cleaned_text = ''
        for char in text.text:
            try:
                char.encode('utf-8').decode('utf-8')
                cleaned_text += char
            except (UnicodeDecodeError, UnicodeEncodeError):
                # Replace problematic character with a space or skip it
                cleaned_text += ' '

        text.text = cleaned_text.strip()

    # Save if text was modified
    if text.text != original_text:
        text.save()
        messages.info(request, 'Text has been normalized for better annotation handling.')

    labels = project.labels.all()
    # Show ALL annotations for this text, not just current user's annotations
    annotations = text.annotations.all().order_by('start_index').select_related('label')

    # Clean and validate annotations
    valid_annotations = []
    for ann in annotations:
        try:
            # Check if annotation positions are valid
            if (ann.start_index >= 0 and
                ann.end_index > ann.start_index and
                ann.end_index <= len(text.text)):
                ann.annotated_text = text.text[ann.start_index:ann.end_index]
                ann.label_color = ann.label.color
                valid_annotations.append(ann)
            else:
                # Remove invalid annotation
                ann.delete()
        except (IndexError, TypeError):
            # Remove problematic annotation
            ann.delete()
            continue

    # Create custom JSON structure for JavaScript
    annotations_data = []
    for ann in valid_annotations:
        try:
            annotations_data.append({
                'id': ann.id,
                'start_index': ann.start_index,
                'end_index': ann.end_index,
                'label': ann.label.name,
                'label_color': ann.label.color,
                'annotated_text': ann.annotated_text,
                'suggestions': ann.suggestions or [],
                'user_id': ann.user.id,
                'username': ann.user.username
            })
        except (IndexError, TypeError, AttributeError):
            # Skip problematic annotations
            continue

    # Safely serialize to JSON with error handling
    try:
        annotations_json = json.dumps(annotations_data, ensure_ascii=False)
    except (TypeError, ValueError, UnicodeEncodeError):
        # If JSON serialization fails, create a basic structure
        annotations_json = json.dumps([])
        messages.warning(request, 'Some annotation data could not be loaded due to encoding issues.')

    return render(request, 'text_annotate.html', {
        'project': project,
        'text': text,
        'labels': labels,
        'annotations': valid_annotations,
        'annotations_json': annotations_json
    })

@login_required
def add_annotation(request, user_id, user_project_id, text_id):
    if request.method == 'POST':
        project = get_object_or_404(Project, owner_id=user_id, user_project_id=user_project_id)
        text = get_object_or_404(Text, id=text_id, project=project)
        if project.owner != request.user and not ProjectCollaborator.objects.filter(project=project, user=request.user).exists():
            return JsonResponse({'error': 'No access'}, status=403)

        try:
            start_index = int(request.POST.get('start_index'))
            end_index = int(request.POST.get('end_index'))
            label_id = int(request.POST.get('label_id'))
            suggestions_str = request.POST.get('suggestions', '')
            is_reannotation = request.POST.get('is_reannotation', 'false').lower() == 'true'
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid parameters'}, status=400)

        # Parse suggestions: JSON array from frontend
        suggestions = json.loads(suggestions_str) if suggestions_str else []

        label = get_object_or_404(Label, id=label_id, project=project)

        # Validate indices
        if start_index < 0 or end_index <= start_index or end_index > len(text.text):
            return JsonResponse({'error': 'Invalid text range'}, status=400)

        # Check if there's already an annotation for this exact range by this user
        existing_annotation = Annotation.objects.filter(
            text=text,
            user=request.user,
            start_index=start_index,
            end_index=end_index
        ).first()

        if existing_annotation:
            # Update existing annotation (re-annotation case)
            existing_annotation.label = label
            existing_annotation.suggestions = suggestions
            existing_annotation.is_reannotation = is_reannotation
            existing_annotation.save()
            return JsonResponse({'success': True, 'id': existing_annotation.id, 'updated': True})
        else:
            # Create new annotation
            try:
                annotation = Annotation.objects.create(
                    text=text,
                    user=request.user,
                    start_index=start_index,
                    end_index=end_index,
                    label=label,
                    suggestions=suggestions,
                    is_reannotation=is_reannotation
                )
                return JsonResponse({'success': True, 'id': annotation.id, 'created': True})
            except Exception as e:
                print(f"Error creating annotation: {e}")
                return JsonResponse({'error': f'Failed to create annotation: {str(e)}'}, status=500)
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def update_annotation(request, user_id, user_project_id, text_id, annotation_id):
    if request.method == 'POST':
        project = get_object_or_404(Project, owner_id=user_id, user_project_id=user_project_id)
        text = get_object_or_404(Text, id=text_id, project=project)
        annotation = get_object_or_404(Annotation, id=annotation_id, text=text, user=request.user)
        if project.owner != request.user and not ProjectCollaborator.objects.filter(project=project, user=request.user).exists():
            return JsonResponse({'error': 'No access'}, status=403)

        suggestions_str = request.POST.get('suggestions', '')
        suggestions = json.loads(suggestions_str) if suggestions_str else []
        annotation.suggestions = suggestions
        annotation.save()

        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def delete_annotation(request, annotation_id):
    annotation = get_object_or_404(Annotation, id=annotation_id, user=request.user)
    annotation.delete()
    return JsonResponse({'success': True})

@login_required
def project_collaborators(request, user_id, user_project_id):
    project = get_object_or_404(Project, owner_id=user_id, user_project_id=user_project_id)
    if project.owner != request.user:
        messages.error(request, 'Only the owner can manage collaborators.')
        return redirect('project_detail', user_id=user_id, user_project_id=user_project_id)
    collaborators = project.collaborators.all()
    return render(request, 'project_collaborators.html', {
        'project': project,
        'collaborators': collaborators
    })

@login_required
def add_collaborator(request, user_id, user_project_id):
    print("add_collaborator called")
    project = get_object_or_404(Project, owner_id=user_id, user_project_id=user_project_id)
    # print(project)
    if project.owner != request.user:
        return JsonResponse({'error': 'No permission'}, status=403)
    if request.method == 'POST':
        username = request.POST.get('username')
        try:
            user = User.objects.get(username=username)
            if user == project.owner:
                return JsonResponse({'error': 'Cannot add owner as collaborator'})
            ProjectCollaborator.objects.get_or_create(project=project, user=user)
            return JsonResponse({'success': True})
        except User.DoesNotExist:
            return JsonResponse({'error': 'User not found'})
    return JsonResponse({'error': 'Invalid request'})

@login_required
def remove_collaborator(request, user_id, user_project_id, collaborator_user_id):
    project = get_object_or_404(Project, owner_id=user_id, user_project_id=user_project_id)
    # print(project)
    if project.owner != request.user:
        return JsonResponse({'error': 'No permission'}, status=403)
    collaborator = get_object_or_404(ProjectCollaborator, project=project, user_id=collaborator_user_id)
    collaborator.delete()
    return JsonResponse({'success': True})

@login_required
def export_annotations(request, user_id, user_project_id):
    project = get_object_or_404(Project, owner_id=user_id, user_project_id=user_project_id)
    if project.owner != request.user and not ProjectCollaborator.objects.filter(project=project, user=request.user).exists():
        messages.error(request, 'No access')
        return redirect('home')

    format_type = request.GET.get('format', 'csv')
    annotations = Annotation.objects.filter(text__project=project).select_related('text', 'label', 'user').order_by('text__id', 'start_index')

    if format_type == 'json':
        data = []
        for ann in annotations:
            # Calculate the selected sub text
            try:
                selected_sub_text = ann.text.text[ann.start_index:ann.end_index]
            except (IndexError, TypeError):
                selected_sub_text = ''

            data.append({
                'ID': ann.id,
                'input_text_id': ann.text.text_id,
                'content': ann.text.text,
                'selected_sub_text': selected_sub_text,
                'start_index': ann.start_index,
                'error_label': ann.label.name,
                'suggestions': ann.suggestions or []
            })
        response = JsonResponse(data, safe=False, json_dumps_params={'ensure_ascii': False})
        response['Content-Disposition'] = f'attachment; filename="{project.name}_annotations.json"'
        return response
    else:
        # CSV export
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{project.name}_annotations.csv"'
        writer = csv.writer(response)
        writer.writerow(['ID', 'input_text_id', 'content', 'selected_sub_text', 'start_index', 'error_label', 'suggestions'])
        for ann in annotations:
            # Calculate the selected sub text
            try:
                selected_sub_text = ann.text.text[ann.start_index:ann.end_index]
            except (IndexError, TypeError):
                selected_sub_text = ''
            writer.writerow([
                ann.id,
                ann.text.text_id,
                ann.text.text,
                selected_sub_text,
                ann.start_index,
                ann.label.name,
                json.dumps(ann.suggestions or [], ensure_ascii=False)
            ])
        return response