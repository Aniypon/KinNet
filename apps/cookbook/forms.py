"""ModelForms for the cookbook app."""

from __future__ import annotations

from django import forms

from .models import Recipe


class RecipeForm(forms.ModelForm):
    ingredients = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "rows": 6,
            "placeholder": "Картошка | 4 | шт\nСоль | 1 | ч.л.",
        }),
        label="Ингредиенты (по строке: имя | количество | единица)",
    )

    class Meta:
        model = Recipe
        fields = ["title", "description", "instructions", "cook_time_minutes", "servings", "tags"]
        widgets = {
            "title": forms.TextInput(attrs={"required": True}),
            "description": forms.Textarea(attrs={"rows": 3}),
            "instructions": forms.Textarea(attrs={"rows": 6}),
            "cook_time_minutes": forms.NumberInput(attrs={"min": 0}),
            "servings": forms.NumberInput(attrs={"min": 1}),
            "tags": forms.TextInput(attrs={"placeholder": "ужин, быстрое"}),
        }
        labels = {
            "title": "Название",
            "description": "Описание",
            "instructions": "Инструкция",
            "cook_time_minutes": "Время (мин)",
            "servings": "Сколько порций получится",
            "tags": "Метки (через запятую)",
        }

    def __init__(self, *args, ingredients_text="", **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields["cook_time_minutes"].initial = 30
            self.fields["servings"].initial = 2
        if ingredients_text:
            self.fields["ingredients"].initial = ingredients_text
