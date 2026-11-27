from django import template

register = template.Library()


@register.filter
def initials(name):
    """Up to two initials from the letters and digits of a display name."""
    words = ["".join(ch for ch in word if ch.isalnum()) for word in name.split()]
    return "".join(word[0] for word in words if word)[:2].upper() or "?"
