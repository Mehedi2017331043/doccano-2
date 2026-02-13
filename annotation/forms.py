from django import forms
from .models import Project, Label, Text, Annotation

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description']

class LabelForm(forms.ModelForm):
    color = forms.CharField(
        max_length=7,
        widget=forms.TextInput(attrs={'type': 'color'}),
        help_text='Choose a color for this label'
    )

    class Meta:
        model = Label
        fields = ['name', 'color', 'description']

class TextForm(forms.ModelForm):
    class Meta:
        model = Text
        fields = ['text_id', 'text']

class AnnotationForm(forms.ModelForm):
    suggestions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Enter suggestions, one per line'}),
        help_text='Enter multiple suggestions, one per line'
    )

    class Meta:
        model = Annotation
        fields = ['label', 'start_index', 'end_index', 'suggestions']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Convert list to newline-separated string for display
            self.fields['suggestions'].initial = '\n'.join(self.instance.suggestions or [])

    def clean_suggestions(self):
        suggestions = self.cleaned_data.get('suggestions', '')
        if suggestions:
            # Split by newlines and strip whitespace
            return [s.strip() for s in suggestions.split('\n') if s.strip()]
        return []