from collections import defaultdict

from django.db import migrations


def lowercase_emails(apps, schema_editor):
    """Lowercase stored emails, so login finds accounts saved with capital letters.

    Accounts whose emails differ only by capitalization stop the migration before
    anything changes, because someone has to decide which account to keep.
    """
    User = apps.get_model("accounts", "User")
    users = User.objects.using(schema_editor.connection.alias)

    emails_by_lowercase = defaultdict(list)
    for email in users.values_list("email", flat=True):
        emails_by_lowercase[email.lower()].append(email)
    duplicates = sorted(
        ", ".join(sorted(emails))
        for emails in emails_by_lowercase.values()
        if len(emails) > 1
    )
    if duplicates:
        raise ValueError(
            "Cannot lowercase emails, because these accounts differ only by "
            f"capitalization: {'; '.join(duplicates)}. Change or remove one account "
            "in each group, then run migrate again."
        )

    for pk, email in users.values_list("pk", "email"):
        if email != email.lower():
            users.filter(pk=pk).update(email=email.lower())


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(lowercase_emails, migrations.RunPython.noop),
    ]
