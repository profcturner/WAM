from django import template

register = template.Library()


@register.simple_tag
def active(request, pattern):
    import re
    
    # TODO: This will need special handling, it matches every URL
    #if pattern == '/':
        
    if re.search(pattern, request.path):
        return 'active'
    return ''