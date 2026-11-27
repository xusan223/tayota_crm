from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import StaffProfile

   
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_staff_profile(sender, instance, created, raw=False, **kwargs):
    # ``raw`` saves come from loaddata: the fixture carries the user's real
    # profile, so creating a default one here would collide with it.
    if created and not raw:
        role = (
            StaffProfile.Role.ADMINISTRATOR
            if instance.is_superuser
            else StaffProfile.Role.EMPLOYEE
        )
        StaffProfile.objects.get_or_create(user=instance, defaults={"role": role})
