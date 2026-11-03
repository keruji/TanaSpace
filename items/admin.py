from django.contrib import admin

from .models import Item


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name", "owner__username")

    def save_model(self, request, obj, form, change):
        if change:
            obj.mark_edited(request.user)
        super().save_model(request, obj, form, change)
