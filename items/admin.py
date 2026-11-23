from django.contrib import admin
from django import forms

from .models import Item


class AdminItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = "__all__"

    def clean(self):
        data = super().clean()
        if self.instance.pk:
            original = Item.objects.get(pk=self.instance.pk)
            destination = data.get("item_type")
            if destination and destination.pk != original.item_type_id and original.property_values:
                self.add_error("item_type", "Change this type in the workspace to review and confirm custom value removal.")
        return data


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    form = AdminItemForm
    readonly_fields = ("property_values",)
    list_display = ("name", "owner", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name", "owner__username")

    def save_model(self, request, obj, form, change):
        if change:
            obj.mark_edited(request.user)
        super().save_model(request, obj, form, change)
