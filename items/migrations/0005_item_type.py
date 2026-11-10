from django.db import migrations, models
import django.db.models.deletion


def require_existing_items_to_be_classified(apps, schema_editor):
    Item = apps.get_model("items", "Item")
    database = schema_editor.connection.alias
    if Item.objects.using(database).filter(item_type_id__isnull=True).exists():
        raise RuntimeError(
            "Existing items need a type before this migration can finish. "
            "Assign types in a staged migration; no fallback type is created."
        )


class Migration(migrations.Migration):
    dependencies = [
        ("items", "0004_alter_item_edited_by_alter_item_owner"),
        ("item_types", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="item_type",
            field=models.ForeignKey(
                to="item_types.itemtypes",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="items",
                null=True,
            ),
        ),
        migrations.RunPython(require_existing_items_to_be_classified, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="item",
            name="item_type",
            field=models.ForeignKey(
                to="item_types.itemtypes",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="items",
            ),
        ),
    ]
