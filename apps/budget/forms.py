"""ModelForms for the budget app."""

from __future__ import annotations

from django import forms
from django.utils import timezone

from .models import Expense, Wishlist


class ExpenseForm(forms.ModelForm):
    spent_on = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"],
        widget=forms.DateInput(
            attrs={
                "type": "text",
                "placeholder": "дд.мм.гггг",
                "inputmode": "numeric",
                "autocomplete": "off",
                "data-mask": "date",
            }
        ),
    )

    class Meta:
        model = Expense
        fields = ["title", "amount", "category", "spent_on", "notes"]
        widgets = {
            "title": forms.TextInput(attrs={"required": True}),
            "amount": forms.NumberInput(attrs={"step": "0.01", "required": True}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_spent_on(self):
        value = self.cleaned_data.get("spent_on")
        return value or timezone.localdate()

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is not None and amount <= 0:
            raise forms.ValidationError("Сумма должна быть больше нуля.")
        return amount


class WishlistForm(forms.ModelForm):
    class Meta:
        model = Wishlist
        fields = ["title"]

    def __init__(self, *args, family=None, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
