from django import forms
from django.forms import ModelForm

class TaskCompletionForm(ModelForm):
    class Meta:
        model = TaskCompletion
        fields = ['task', 'staff', 'comment']
