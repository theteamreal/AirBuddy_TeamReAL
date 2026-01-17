from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Template filter to get dictionary item by key
    Usage: {{ my_dict|get_item:key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)