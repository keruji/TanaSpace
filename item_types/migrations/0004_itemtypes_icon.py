from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("item_types", "0003_itemtypes_property_schema_version_itemtypeproperty")]
    operations = [migrations.AddField(
        model_name="itemtypes", name="icon",
        field=models.CharField(choices=(('1F4E6', 'Package'), ('1F4DA', 'Books'), ('1F4D6', 'Book'), ('1F4D3', 'Notebook'), ('1F4DD', 'Memo'), ('1F4C1', 'Folder'), ('1F4C4', 'Document'), ('1F4CC', 'Pin'), ('1F5C2', 'Card index'), ('1F5C3', 'Card file'), ('1F4BB', 'Laptop'), ('1F5A5', 'Computer'), ('1F4F1', 'Phone'), ('1F4F7', 'Camera'), ('1F3A7', 'Headphones'), ('1F50B', 'Battery'), ('1F50C', 'Plug'), ('1F4A1', 'Light bulb'), ('1F527', 'Wrench'), ('1F528', 'Hammer'), ('1FA9B', 'Screwdriver'), ('1F6E0', 'Tools'), ('1F9F0', 'Toolbox'), ('2699', 'Gear'), ('1F511', 'Key'), ('1F512', 'Lock'), ('1F4A7', 'Water'), ('1F331', 'Plant'), ('1F33F', 'Herb'), ('1F375', 'Cup'), ('1F374', 'Cutlery'), ('1F37D', 'Plate'), ('1F455', 'Shirt'), ('1F45F', 'Shoe'), ('1F392', 'Backpack'), ('1F9F3', 'Luggage'), ('231A', 'Watch'), ('1F48D', 'Ring'), ('1F3AE', 'Game controller'), ('1F3B5', 'Music'), ('1F3A8', 'Art'), ('1F381', 'Gift'), ('1F3E0', 'Home'), ('1F6B2', 'Bicycle'), ('1F697', 'Car'), ('1F3C0', 'Basketball'), ('1F9F8', 'Teddy bear'), ('1F9F9', 'Broom')), default="1F4E6", db_default="1F4E6", max_length=16),
    )]
